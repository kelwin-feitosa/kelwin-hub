"""Local-first authenticated API; no external messages or third-party credentials."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import asyncio
import hmac
import logging
import os
import re
from pathlib import Path
import sqlite3
import time
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .security import csrf_token, hash_password, sign_session, validate_session, verify_password, SESSION_SECONDS
from .storage import Store, now_utc, new_id, rows, record
from .automation import TEMPLATES, safe_run_stale
from .workspace import load_workspace
from .search import search as search_records
from .project_context import load_project_context
from .nexo_context import load_opportunity_context
from .nexo_insights import load_suggestions
from .opportunity_board import load_board
from .transcripts import validate_text, segments, MAX_TRANSCRIPT_BYTES

LOG = logging.getLogger(__name__)
STATIC = Path(__file__).parent / 'static'
LOCAL_TZ = ZoneInfo('America/Sao_Paulo')
# Fixed-length decimal amounts only: protect Decimal/int conversion and SQLite storage.
_MONEY_FORMAT = re.compile(r'[0-9]{1,10}(?:\.[0-9]{1,2})?\Z')


def timestamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=LOCAL_TZ)
        return parsed.astimezone(timezone.utc).isoformat(timespec='seconds')
    except ValueError:
        raise HTTPException(422, 'Data ISO inválida')


def money(value: str | None) -> int | None:
    if value in (None, ''):
        return None
    # Do not pass unbounded, exponent or non-finite inputs to Decimal/int.
    # Ten integer digits are ample for the personal CRM and fit SQLite INTEGER cents.
    if not isinstance(value, str) or not _MONEY_FORMAT.fullmatch(value):
        raise HTTPException(422, 'Valor em reais inválido (até 10 dígitos e duas casas decimais)')
    return int(Decimal(value) * 100)


def normalized_email(raw: str | None):
    if not raw or not raw.strip():
        return None
    value = raw.strip().lower()
    if ' ' in value or value.count('@') != 1 or '.' not in value.split('@')[1] or len(value) > 254:
        raise HTTPException(422, 'E-mail inválido')
    return value


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


def required_text(value: str) -> str:
    """Normalize Unicode whitespace and refuse empty user-facing required fields."""
    normalized = value.strip()
    if not normalized:
        raise ValueError('Campo obrigatório não pode ficar vazio')
    return normalized


class Login(Strict):
    password: str

class ProjectIn(Strict):
    name: str = Field(min_length=1,max_length=150)
    area: str = Field(default='pessoal',min_length=1,max_length=80)

    @field_validator('name', 'area')
    @classmethod
    def required(cls, value: str) -> str:
        return required_text(value)

class ProjectUpdate(Strict):
    name: str | None = Field(default=None,min_length=1,max_length=150)
    area: str | None = Field(default=None,min_length=1,max_length=80)
    status: str | None = None

class ContactUpdate(Strict):
    name: str | None = Field(default=None,min_length=1,max_length=150)
    company: str | None = Field(default=None,max_length=150)
    email: str | None = Field(default=None,max_length=254)
    phone: str | None = Field(default=None,max_length=60)
    category: str | None = Field(default=None,max_length=80)

class ContactIn(Strict):
    name: str = Field(min_length=1,max_length=150)

    @field_validator('name')
    @classmethod
    def required(cls, value: str) -> str:
        return required_text(value)
    company: str = Field(default='',max_length=150)
    email: str | None = Field(default=None,max_length=254)
    phone: str = Field(default='',max_length=60)
    category: str = Field(default='business',max_length=80)

class OpportunityIn(Strict):
    @field_validator('title', 'next_action')
    @classmethod
    def required(cls, value: str) -> str:
        return required_text(value)

    contact_id: str
    title: str = Field(min_length=1,max_length=180)
    kind: str = Field(default='service',max_length=80)
    next_action: str = Field(min_length=1,max_length=300)
    followup_at: str | None = None
    value_brl: str | None = None

class OpportunityUpdate(Strict):
    title: str | None = Field(default=None,min_length=1,max_length=180)
    next_action: str | None = Field(default=None,max_length=300)
    status: str | None = None
    followup_at: str | None = None
    value_brl: str | None = None

class TaskIn(Strict):
    title: str = Field(min_length=1,max_length=200)

    @field_validator('title')
    @classmethod
    def required(cls, value: str) -> str:
        return required_text(value)
    project_id: str | None = None
    opportunity_id: str | None = None
    priority: int = Field(default=1,ge=0,le=3)
    due_at: str | None = None
    next_action: str = Field(default='',max_length=300)

class TaskUpdate(Strict):
    status: str | None = None
    title: str | None = Field(default=None,min_length=1,max_length=200)
    due_at: str | None = None
    priority: int | None = Field(default=None,ge=0,le=3)
    next_action: str | None = Field(default=None,max_length=300)

class EventIn(Strict):
    title: str = Field(min_length=1,max_length=180)

    @field_validator('title')
    @classmethod
    def required(cls, value: str) -> str:
        return required_text(value)
    start_at: str
    end_at: str
    status: str = 'confirmed'
    project_id: str | None = None
    contact_id: str | None = None

class EventUpdate(Strict):
    status: str | None = None
    title: str | None = Field(default=None,min_length=1,max_length=180)
    start_at: str | None = None
    end_at: str | None = None
    project_id: str | None = None
    contact_id: str | None = None

class NoteIn(Strict):
    title: str = Field(min_length=1,max_length=160)
    body: str = Field(min_length=1,max_length=12000)
    project_id: str | None = None
    contact_id: str | None = None
    opportunity_id: str | None = None

    @field_validator('title', 'body')
    @classmethod
    def required(cls, value: str) -> str:
        return required_text(value)

class NoteUpdate(Strict):
    title: str | None = Field(default=None,min_length=1,max_length=160)
    body: str | None = Field(default=None,min_length=1,max_length=12000)

class TranscriptIn(Strict):
    format: str
    content: str = Field(min_length=1,max_length=200000)
    source_name: str = Field(default='',max_length=180)

class AutomationIn(Strict):
    enabled: bool
    threshold_days: int = Field(ge=1,le=365)


def create_app(database_path: str | None = None, *, password_hash: str | None = None,
               session_secret: str | None = None, internal_token: str | None = None,
               scheduler: bool | None = None) -> FastAPI:
    path = database_path or os.getenv('HUB_DB_PATH', './data/hub.db')
    passwd = password_hash or os.getenv('HUB_PASSWORD_HASH')
    secret = session_secret or os.getenv('HUB_SESSION_SECRET')
    internal = internal_token if internal_token is not None else os.getenv('HUB_INTERNAL_TOKEN', '')
    if not passwd or not secret or len(secret) < 32:
        raise RuntimeError('Configure HUB_PASSWORD_HASH e HUB_SESSION_SECRET com scripts/init_env.py')
    store = Store(path)
    attempts: dict[str,list[float]] = {}
    scheduler_on = scheduler if scheduler is not None else os.getenv('HUB_SCHEDULER','1') == '1'

    def scheduler_tick():
        """One catch-up step: on startup/run it checks persisted due time."""
        try:
            with store.connection() as db:
                conf = db.execute("SELECT last_run_at,enabled FROM automation_configs WHERE code='stale_opportunities'").fetchone()
            if conf and conf['enabled'] and (
                not conf['last_run_at'] or
                datetime.now(timezone.utc) - datetime.fromisoformat(conf['last_run_at']) >= timedelta(minutes=30)
            ):
                safe_run_stale(store)
            with store.transaction() as db:
                db.execute("UPDATE scheduler_health SET last_check_at=?,last_success_at=?,last_failure_type=NULL WHERE id=1",
                           (now_utc(), now_utc()))
        except Exception as exc:
            # Never record exception messages: they might contain user data/SQL.
            LOG.warning('scheduler_tick_failed type=%s', type(exc).__name__)
            try:
                with store.transaction() as db:
                    db.execute('UPDATE scheduler_health SET last_check_at=?,last_failure_at=?,last_failure_type=? WHERE id=1',
                               (now_utc(),now_utc(),type(exc).__name__))
            except Exception as persist_exc:
                LOG.warning('scheduler_health_unavailable type=%s', type(persist_exc).__name__)

    async def scheduled():
        while True:
            await asyncio.to_thread(scheduler_tick)
            await asyncio.sleep(60)

    @asynccontextmanager
    async def lifespan(app):
        job = asyncio.create_task(scheduled()) if scheduler_on else None
        try:
            yield
        finally:
            if job:
                job.cancel()
                try:
                    await job
                except asyncio.CancelledError:
                    pass

    app = FastAPI(title='Kelwin Hub piloto', version='0.1.0', lifespan=lifespan, docs_url=None, redoc_url=None)
    # Reject DNS-rebinding and unexpected Host headers before any routes.
    # 'hub' is Docker Compose, and 'testserver' is FastAPI's TestClient.
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=['127.0.0.1', 'localhost', 'hub', 'testserver'],
        www_redirect=False,
    )
    app.state.store = store
    app.mount('/static', StaticFiles(directory=str(STATIC)), name='static')

    def active_nonce(req: Request) -> str | None:
        nonce = validate_session(secret, req.cookies.get('kh_session'))
        if not nonce:
            return None
        with store.connection() as db:
            active = db.execute('SELECT 1 FROM sessions WHERE nonce=? AND revoked_at IS NULL AND expires_at>?',
                                (nonce, int(time.time()))).fetchone()
        return nonce if active else None

    def require_login(req: Request):
        nonce = active_nonce(req)
        if not nonce:
            raise HTTPException(401,'Faça login para acessar o Hub')
        if req.method in {'POST','PUT','PATCH','DELETE'}:
            got = req.headers.get('x-csrf-token','')
            if not hmac.compare_digest(got,csrf_token(secret,nonce)):
                raise HTTPException(403,'Token de proteção inválido')
        return nonce

    def same_origin(req: Request):
        origin = req.headers.get('origin')
        if origin and origin.rstrip('/') != f'{req.url.scheme}://{req.headers.get("host")}'.rstrip('/'):
            raise HTTPException(403,'Origem não autorizada')

    @app.middleware('http')
    async def headers(req, call_next):
        if req.method in {'POST','PUT','PATCH','DELETE'}:
            try:
                same_origin(req)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code,content={"detail":exc.detail})
        resp = await call_next(req)
        resp.headers['X-Content-Type-Options']='nosniff'
        resp.headers['X-Frame-Options']='DENY'
        resp.headers['Referrer-Policy']='no-referrer'
        resp.headers['Cache-Control']='no-store'
        resp.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        return resp

    @app.get('/')
    def page():
        return FileResponse(STATIC/'index.html')

    @app.get('/favicon.ico', include_in_schema=False)
    def favicon():
        return FileResponse(STATIC / 'favicon.svg', media_type='image/svg+xml')

    @app.get('/healthz')
    def health():
        try:
            with store.connection() as db:
                db.execute('SELECT 1').fetchone()
            return {'status':'ok','component':'hub','n8n':'not_checked'}
        except sqlite3.Error:
            return JSONResponse(status_code=503, content={'status':'degraded','component':'hub'})

    @app.post('/api/login')
    def login(data: Login, req: Request, response: Response):
        addr = req.client.host if req.client else 'local'
        current = time.monotonic()
        attempts[addr] = [t for t in attempts.get(addr,[]) if current-t < 60]
        if len(attempts[addr]) >= 5:
            raise HTTPException(429,'Muitas tentativas. Tente novamente depois.')
        if not verify_password(data.password,passwd):
            attempts[addr].append(current)
            raise HTTPException(401,'Senha incorreta')
        attempts.pop(addr,None)
        cookie = sign_session(secret)
        nonce = validate_session(secret, cookie)
        with store.transaction() as db:
            db.execute('DELETE FROM sessions WHERE expires_at<=?', (int(time.time()),))
            db.execute('INSERT INTO sessions(nonce,created_at,expires_at) VALUES (?,?,?)',
                       (nonce,now_utc(),int(time.time())+SESSION_SECONDS))
        response.set_cookie('kh_session',cookie,max_age=SESSION_SECONDS,
                            httponly=True,samesite='strict',secure=os.getenv('HUB_COOKIE_SECURE')=='1',path='/')
        return {'ok':True}

    @app.get('/api/session')
    def session(req: Request):
        nonce = active_nonce(req)
        return {'authenticated':bool(nonce),'csrf':csrf_token(secret,nonce) if nonce else None}

    @app.post('/api/logout')
    def logout(response: Response, nonce=Depends(require_login)):
        with store.transaction() as db:
            db.execute('UPDATE sessions SET revoked_at=? WHERE nonce=? AND revoked_at IS NULL', (now_utc(),nonce))
        response.delete_cookie('kh_session',path='/')
        return {'ok':True}

    @app.get('/api/nexo/suggestions')
    def nexo_suggestions(_=Depends(require_login)):
        return load_suggestions(store)

    @app.get('/api/workspace')
    def workspace(_=Depends(require_login)):
        return load_workspace(store)

    @app.get('/api/search')
    def universal_search(q: str, _=Depends(require_login)):
        try:
            return search_records(store, q)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get('/api/dashboard')
    def dashboard(_=Depends(require_login)):
        begin = datetime.now(LOCAL_TZ).replace(hour=0,minute=0,second=0,microsecond=0)
        end = begin + timedelta(days=1)
        with store.connection() as db:
            return {
                'totals': {
                    'projects': db.execute("SELECT COUNT(*) FROM projects WHERE status='active'").fetchone()[0],
                    'tasks': db.execute("SELECT COUNT(*) FROM tasks WHERE status!='done'").fetchone()[0],
                    'contacts': db.execute('SELECT COUNT(*) FROM contacts').fetchone()[0],
                    'opportunities':db.execute("SELECT COUNT(*) FROM opportunities WHERE status IN ('new','active','waiting')").fetchone()[0],
                    'alerts':db.execute("SELECT COUNT(*) FROM alerts WHERE status='open'").fetchone()[0],
                },
                'tasks': rows(db.execute("SELECT * FROM tasks WHERE status!='done' ORDER BY CASE WHEN due_at IS NULL THEN 1 ELSE 0 END, due_at, priority DESC LIMIT 12")),
                'events': rows(db.execute("SELECT * FROM events WHERE start_at>=? AND start_at<? AND status!='cancelled' ORDER BY start_at",(timestamp(begin.isoformat()),timestamp(end.isoformat())))),
                'alerts':rows(db.execute("SELECT * FROM alerts WHERE status='open' ORDER BY created_at DESC LIMIT 10")),
            }

    @app.get('/api/projects')
    def projects(_=Depends(require_login)):
        with store.connection() as db:
            return rows(db.execute('SELECT * FROM projects ORDER BY created_at DESC'))

    @app.get('/api/projects/{ident}/context')
    def project_context(ident: str, _=Depends(require_login)):
        data = load_project_context(store, ident)
        if data is None:
            raise HTTPException(404, 'Projeto não encontrado')
        return data

    @app.post('/api/projects',status_code=201)
    def add_project(data: ProjectIn,_=Depends(require_login)):
        ident=new_id()
        with store.transaction() as db:
            db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',(ident,data.name.strip(),data.area.strip(),'active',now_utc()))
            record(db,'project',ident,'create')
        return {'id':ident}

    @app.patch('/api/projects/{ident}')
    def edit_project(ident: str,data: ProjectUpdate,_=Depends(require_login)):
        updates=data.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(422,'Nenhuma alteração informada')
        if 'status' in updates and updates['status'] not in ('active','paused','completed','archived'):
            raise HTTPException(422,'Status inválido')
        for key in ('name','area'):
            if key in updates and (updates[key] is None or not updates[key].strip()):
                raise HTTPException(422,'Campo obrigatório não pode ficar vazio')
            if key in updates: updates[key]=updates[key].strip()
        with store.transaction() as db:
            result=db.execute('UPDATE projects SET '+','.join(f'{key}=?' for key in updates)+' WHERE id=?',
                (*updates.values(),ident))
            if not result.rowcount: raise HTTPException(404,'Projeto não encontrado')
            record(db,'project',ident,'update')
        return {'ok':True}

    @app.get('/api/contacts')
    def contacts(_=Depends(require_login)):
        with store.connection() as db:
            return rows(db.execute('SELECT * FROM contacts ORDER BY created_at DESC'))

    @app.post('/api/contacts',status_code=201)
    def add_contact(data: ContactIn,_=Depends(require_login)):
        ident=new_id()
        email=normalized_email(data.email)
        try:
            with store.transaction() as db:
                db.execute('INSERT INTO contacts VALUES (?,?,?,?,?,?,?,?)',
                    (ident,data.name.strip(),data.company.strip(),email,data.phone.strip(),data.category.strip(),'manual',now_utc()))
                record(db,'contact',ident,'create')
        except sqlite3.IntegrityError:
            raise HTTPException(409,'Contato com este e-mail já existe')
        return {'id':ident}

    @app.patch('/api/contacts/{ident}')
    def edit_contact(ident: str,data: ContactUpdate,_=Depends(require_login)):
        updates=data.model_dump(exclude_unset=True)
        if not updates: raise HTTPException(422,'Nenhuma alteração informada')
        if 'email' in updates: updates['email']=normalized_email(updates['email'])
        for key in ('name','company','phone','category'):
            if key in updates:
                if updates[key] is None or (key=='name' and not updates[key].strip()):
                    raise HTTPException(422,'Campo inválido')
                updates[key]=updates[key].strip()
        try:
            with store.transaction() as db:
                result=db.execute('UPDATE contacts SET '+','.join(f'{key}=?' for key in updates)+' WHERE id=?',(*updates.values(),ident))
                if not result.rowcount:raise HTTPException(404,'Contato não encontrado')
                record(db,'contact',ident,'update')
        except sqlite3.IntegrityError:
            raise HTTPException(409,'Outro contato possui este e-mail')
        return {'ok':True}

    @app.get('/api/opportunities')
    def opportunities(_=Depends(require_login)):
        with store.connection() as db:
            return rows(db.execute('''SELECT o.*, c.name AS contact_name, c.email AS contact_email
                FROM opportunities o JOIN contacts c ON c.id=o.contact_id ORDER BY o.created_at DESC'''))

    @app.get('/api/opportunities/{ident}/context')
    def opportunity_context(ident: str, _=Depends(require_login)):
        data = load_opportunity_context(store, ident)
        if data is None:
            raise HTTPException(404, 'Oportunidade não encontrada')
        return data

    @app.get('/api/opportunities/board')
    def opportunity_board(_=Depends(require_login)):
        return load_board(store)

    @app.post('/api/opportunities',status_code=201)
    def add_opportunity(data: OpportunityIn,_=Depends(require_login)):
        ident=new_id(); n=now_utc()
        with store.transaction() as db:
            if not db.execute('SELECT 1 FROM contacts WHERE id=?',(data.contact_id,)).fetchone():
                raise HTTPException(404,'Contato não encontrado')
            db.execute('INSERT INTO opportunities VALUES (?,?,?,?,?,?,?,?,?,?,?)',(
                ident,data.contact_id,data.title.strip(),data.kind.strip(),'new',money(data.value_brl),
                data.next_action.strip(),timestamp(data.followup_at),None,n,n))
            record(db,'opportunity',ident,'create')
        return {'id':ident}

    @app.patch('/api/opportunities/{ident}')
    def edit_opportunity(ident: str,data: OpportunityUpdate,_=Depends(require_login)):
        updates=data.model_dump(exclude_unset=True)
        if not updates: raise HTTPException(422,'Nenhuma alteração informada')
        if 'status' in updates and updates['status'] not in ('new','active','waiting','won','lost','archived'):
            raise HTTPException(422,'Status inválido')
        if 'title' in updates:
            if updates['title'] is None or not updates['title'].strip():raise HTTPException(422,'Título inválido')
            updates['title']=updates['title'].strip()
        if 'next_action' in updates:
            if updates['next_action'] is None:raise HTTPException(422,'Próxima ação inválida')
            if not updates['next_action'].strip():
                raise HTTPException(422,'Próxima ação não pode ficar vazia')
            updates['next_action']=updates['next_action'].strip()
        if 'followup_at' in updates:updates['followup_at']=timestamp(updates['followup_at'])
        if 'value_brl' in updates:updates['value_cents']=money(updates.pop('value_brl'))
        updates['updated_at']=now_utc()
        with store.transaction() as db:
            result=db.execute('UPDATE opportunities SET '+','.join(f'{key}=?' for key in updates)+' WHERE id=?',(*updates.values(),ident))
            if not result.rowcount:raise HTTPException(404,'Oportunidade não encontrada')
            if updates.get('status') in ('won','lost','archived'):
                db.execute("UPDATE alerts SET status='resolved',closed_at=? WHERE code='stale_opportunities' AND entity_id=? AND status='open'",(now_utc(),ident))
            record(db,'opportunity',ident,'update')
        return {'ok':True}

    @app.post('/api/opportunities/{ident}/contact')
    def mark_contact(ident: str,_=Depends(require_login)):
        with store.transaction() as db:
            if not db.execute('SELECT 1 FROM opportunities WHERE id=?',(ident,)).fetchone():
                raise HTTPException(404,'Oportunidade não encontrada')
            db.execute("UPDATE opportunities SET last_contact_at=?,updated_at=?,status='active' WHERE id=?",(now_utc(),now_utc(),ident))
            db.execute("UPDATE alerts SET status='resolved',closed_at=? WHERE code='stale_opportunities' AND entity_id=? AND status='open'",(now_utc(),ident))
            record(db,'opportunity',ident,'contact_recorded')
        return {'ok':True}

    @app.get('/api/tasks')
    def tasks(_=Depends(require_login)):
        with store.connection() as db:
            return rows(db.execute('SELECT * FROM tasks ORDER BY status, due_at, created_at DESC'))

    @app.post('/api/tasks',status_code=201)
    def add_task(data: TaskIn,_=Depends(require_login)):
        ident=new_id()
        with store.transaction() as db:
            if data.project_id and not db.execute('SELECT 1 FROM projects WHERE id=?',(data.project_id,)).fetchone():
                raise HTTPException(404,'Projeto não encontrado')
            if data.opportunity_id and not db.execute('SELECT 1 FROM opportunities WHERE id=?',(data.opportunity_id,)).fetchone():
                raise HTTPException(404,'Oportunidade não encontrada')
            db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)',(
                ident,data.title.strip(),data.project_id,data.opportunity_id,'open',data.priority,
                timestamp(data.due_at),data.next_action.strip(),None,now_utc()))
            record(db,'task',ident,'create')
        return {'id':ident}

    @app.patch('/api/tasks/{ident}')
    def update_task(ident: str,data: TaskUpdate,_=Depends(require_login)):
        updates=data.model_dump(exclude_unset=True)
        if not updates:raise HTTPException(422,'Nenhuma alteração informada')
        if 'status' in updates:
            if updates['status'] not in ('open','blocked','done'):
                raise HTTPException(422,'Status inválido')
            updates['completed_at']=now_utc() if updates['status']=='done' else None
        if 'due_at' in updates:updates['due_at']=timestamp(updates['due_at'])
        for key in ('title','next_action'):
            if key in updates:
                if updates[key] is None or (key=='title' and not updates[key].strip()):
                    raise HTTPException(422,'Campo inválido')
                updates[key]=updates[key].strip()
        with store.transaction() as db:
            result=db.execute('UPDATE tasks SET '+','.join(f'{key}=?' for key in updates)+' WHERE id=?',(*updates.values(),ident))
            if not result.rowcount:raise HTTPException(404,'Tarefa não encontrada')
            record(db,'task',ident,'update')
        return {'ok':True}

    @app.get('/api/notes')
    def notes(project_id: str | None = None, contact_id: str | None = None,
              opportunity_id: str | None = None, limit: int = 100, offset: int = 0,
              _=Depends(require_login)):
        if not 1 <= limit <= 100 or not 0 <= offset <= 100_000:
            raise HTTPException(422,'Paginação inválida')
        terms=[]; params=[]
        for field,ident in (('project_id',project_id),('contact_id',contact_id),('opportunity_id',opportunity_id)):
            if ident is not None:
                terms.append(f'{field}=?');params.append(ident)
        sql='SELECT * FROM notes'+(' WHERE '+' AND '.join(terms) if terms else '')+' ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?'
        with store.connection() as db:
            return rows(db.execute(sql,(*params,limit,offset)))

    @app.post('/api/notes',status_code=201)
    def add_note(data: NoteIn,_=Depends(require_login)):
        ident=new_id(); now=now_utc()
        with store.transaction() as db:
            for table,related in (('projects',data.project_id),('contacts',data.contact_id),('opportunities',data.opportunity_id)):
                if related is not None and not db.execute(f'SELECT 1 FROM {table} WHERE id=?',(related,)).fetchone():
                    raise HTTPException(404,'Contexto não encontrado')
            db.execute('INSERT INTO notes VALUES (?,?,?,?,?,?,?,?)',
                       (ident,data.title,data.body,data.project_id,data.contact_id,data.opportunity_id,now,now))
            record(db,'note',ident,'create')
        return {'id':ident}

    @app.patch('/api/notes/{ident}')
    def edit_note(ident: str,data: NoteUpdate,_=Depends(require_login)):
        changes=data.model_dump(exclude_unset=True)
        if not changes or any(not isinstance(v,str) or not v.strip() for v in changes.values()):
            raise HTTPException(422,'Nenhuma alteração válida')
        changes={key:value.strip() for key,value in changes.items()}
        changes['updated_at']=now_utc()
        with store.transaction() as db:
            updated=db.execute('UPDATE notes SET '+','.join(f'{field}=?' for field in changes)+' WHERE id=?',
                               (*changes.values(),ident))
            if not updated.rowcount:raise HTTPException(404,'Nota não encontrada')
            record(db,'note',ident,'update')
        return {'ok':True}

    @app.get('/api/activity')
    def contextual_activity(kind: str, ident: str, limit: int = 40, offset: int = 0,
                            _=Depends(require_login)):
        sources={'project':('projects','project_id'),'opportunity':('opportunities','opportunity_id'),
                 'contact':('contacts','contact_id')}
        if kind not in sources or not 1 <= limit <= 100 or not 0 <= offset <= 100_000:
            raise HTTPException(422,'Contexto ou paginação inválidos')
        table, link=sources[kind]
        with store.connection() as db:
            if not db.execute(f'SELECT 1 FROM {table} WHERE id=?',(ident,)).fetchone():
                raise HTTPException(404,'Contexto não encontrado')
            # Audit rows are existing factual operation records, not inferred history.
            clauses=['(a.kind=? AND a.entity_id=?)']; params=[kind,ident]
            clauses.append(f"(a.kind='note' AND a.entity_id IN (SELECT n.id FROM notes n WHERE n.{link}=?))")
            params.append(ident)
            if kind in ('project','contact'):
                clauses.append(f"(a.kind='event' AND a.entity_id IN (SELECT e.id FROM events e WHERE e.{link}=?))")
                params.append(ident)
                clauses.append(f"(a.kind='transcript' AND a.entity_id IN (SELECT m.id FROM meeting_transcripts m JOIN events e ON e.id=m.event_id WHERE e.{link}=?))")
                params.append(ident)
            if kind in ('project','opportunity'):
                clauses.append(f"(a.kind='task' AND a.entity_id IN (SELECT t.id FROM tasks t WHERE t.{link}=?))")
                params.append(ident)
            result=db.execute('SELECT a.* FROM audit a WHERE '+' OR '.join(clauses)+
                              ' ORDER BY a.at DESC,a.id DESC LIMIT ? OFFSET ?',(*params,limit,offset))
            return rows(result)

    def check_event_links(db, project_id: str | None, contact_id: str | None):
        for table,related in (('projects',project_id),('contacts',contact_id)):
            if related and not db.execute(f'SELECT 1 FROM {table} WHERE id=?',(related,)).fetchone():
                raise HTTPException(404,'Vínculo do evento não encontrado')

    def check_event_conflict(db, start: str, end: str, ident: str | None = None):
        # Checked inside BEGIN IMMEDIATE: concurrent confirmed bookings serialize.
        blocked=db.execute("SELECT id FROM events WHERE status='confirmed' AND start_at<? AND end_at>? AND id!=? LIMIT 1",
                           (end,start,ident or '')).fetchone()
        if blocked:
            raise HTTPException(409,'Horário ocupado por outro evento confirmado')

    @app.get('/api/events')
    def events(_=Depends(require_login)):
        with store.connection() as db:
            return rows(db.execute('SELECT * FROM events ORDER BY start_at'))

    @app.get('/api/events/conflicts')
    def event_conflicts(start_at: str,end_at: str,ignore_id: str | None=None,_=Depends(require_login)):
        start=timestamp(start_at);end=timestamp(end_at)
        if start>=end:raise HTTPException(422,'Intervalo inválido')
        with store.connection() as db:
            overlaps=rows(db.execute("SELECT id,title,start_at,end_at FROM events WHERE status='confirmed' AND start_at<? AND end_at>? AND id!=? ORDER BY start_at LIMIT 30",
                                    (end,start,ignore_id or '')))
        return {'available':not overlaps,'conflicts':overlaps}

    @app.post('/api/events',status_code=201)
    def add_event(data: EventIn,_=Depends(require_login)):
        if data.status not in ('proposed','confirmed'):
            raise HTTPException(422,'Status inválido')
        start=timestamp(data.start_at);end=timestamp(data.end_at)
        if start>=end:raise HTTPException(422,'O evento deve terminar depois do início')
        ident=new_id()
        with store.transaction() as db:
            check_event_links(db,data.project_id,data.contact_id)
            if data.status=='confirmed':check_event_conflict(db,start,end)
            db.execute('INSERT INTO events(id,title,start_at,end_at,status,source,created_at,project_id,contact_id) VALUES (?,?,?,?,?,?,?,?,?)',
                (ident,data.title.strip(),start,end,data.status,'local',now_utc(),data.project_id,data.contact_id))
            record(db,'event',ident,'create')
        return {'id':ident}

    @app.patch('/api/events/{ident}')
    def edit_event(ident:str,data:EventUpdate,_=Depends(require_login)):
        changes=data.model_dump(exclude_unset=True)
        if not changes:raise HTTPException(422,'Nenhuma alteração informada')
        if 'status' in changes and changes['status'] not in ('proposed','confirmed','cancelled'):
            raise HTTPException(422,'Status inválido')
        if 'title' in changes and (changes['title'] is None or not changes['title'].strip()):
            raise HTTPException(422,'Título inválido')
        if 'title' in changes:changes['title']=changes['title'].strip()
        if any(key in changes and (changes[key] is None or not str(changes[key]).strip()) for key in ('start_at','end_at')):
            raise HTTPException(422,'Data obrigatória inválida')
        with store.transaction() as db:
            old=db.execute('SELECT * FROM events WHERE id=?',(ident,)).fetchone()
            if old is None:raise HTTPException(404,'Evento não encontrado')
            start=timestamp(changes['start_at']) if 'start_at' in changes else old['start_at']
            end=timestamp(changes['end_at']) if 'end_at' in changes else old['end_at']
            if start>=end:raise HTTPException(422,'O evento deve terminar depois do início')
            status=changes.get('status',old['status'])
            project_id=changes.get('project_id',old['project_id'])
            contact_id=changes.get('contact_id',old['contact_id'])
            check_event_links(db,project_id,contact_id)
            if status=='confirmed':check_event_conflict(db,start,end,ident)
            changes.update(start_at=start,end_at=end)
            db.execute('UPDATE events SET '+','.join(f'{key}=?' for key in changes)+' WHERE id=?',(*changes.values(),ident))
            record(db,'event',ident,'update')
        return {'ok':True}

    @app.get('/api/events/{ident}/transcripts')
    def event_transcripts(ident: str,_=Depends(require_login)):
        with store.connection() as db:
            if not db.execute('SELECT 1 FROM events WHERE id=?',(ident,)).fetchone():
                raise HTTPException(404,'Compromisso não encontrado')
            return rows(db.execute("SELECT id,event_id,format,source_name,created_at,substr(content,1,160) AS preview FROM meeting_transcripts WHERE event_id=? ORDER BY created_at DESC,id DESC LIMIT 100",(ident,)))

    @app.post('/api/events/{ident}/transcripts',status_code=201)
    def add_transcript(ident: str,data: TranscriptIn,_=Depends(require_login)):
        try:
            text=validate_text(data.content,data.format)
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
        trans_id=new_id()
        with store.transaction() as db:
            if not db.execute('SELECT 1 FROM events WHERE id=?',(ident,)).fetchone():
                raise HTTPException(404,'Compromisso não encontrado')
            db.execute('INSERT INTO meeting_transcripts VALUES (?,?,?,?,?,?)',
                       (trans_id,ident,data.format,data.source_name.strip(),text,now_utc()))
            record(db,'transcript',trans_id,'import')
        return {'id':trans_id}

    @app.get('/api/transcripts/{ident}')
    def transcript_detail(ident: str,_=Depends(require_login)):
        with store.connection() as db:
            raw=db.execute('SELECT * FROM meeting_transcripts WHERE id=?',(ident,)).fetchone()
            if raw is None:raise HTTPException(404,'Transcrição não encontrada')
            doc=dict(raw)
        doc['segments']=segments(doc['content'],doc['format'])
        return doc

    @app.get('/api/automations')
    def automations(_=Depends(require_login)):
        with store.connection() as db:
            available={r['code']:dict(r) for r in db.execute('SELECT * FROM automation_configs')}
            results=[]
            for template in TEMPLATES:
                result={**template,'settings':available.get(template['code'])}
                results.append(result)
            return results

    @app.patch('/api/automations/stale_opportunities')
    def configure_automation(data:AutomationIn,_=Depends(require_login)):
        with store.transaction() as db:
            db.execute('UPDATE automation_configs SET enabled=?,threshold_days=? WHERE code=?',
                       (int(data.enabled),data.threshold_days,'stale_opportunities'))
            record(db,'automation','stale_opportunities','configure')
        return {'ok':True}

    @app.post('/api/automations/stale_opportunities/run')
    def run_automation(_=Depends(require_login)):
        return safe_run_stale(store)

    @app.post('/api/internal/automations/stale_opportunities/run')
    def run_automation_internal(req:Request):
        if not internal or not hmac.compare_digest(req.headers.get('x-hub-internal-token',''),internal):
            raise HTTPException(401,'Não autorizado')
        return safe_run_stale(store)

    @app.get('/api/automation-health')
    def automation_health(_=Depends(require_login)):
        with store.connection() as db:
            health = db.execute('SELECT * FROM scheduler_health WHERE id=1').fetchone()
            config = db.execute("SELECT enabled,last_run_at FROM automation_configs WHERE code='stale_opportunities'").fetchone()
        return {**dict(health), 'scheduler_enabled':scheduler_on,
                'automation_enabled':bool(config['enabled']), 'last_run_at':config['last_run_at']}

    @app.get('/api/automation-runs')
    def runs(_=Depends(require_login)):
        with store.connection() as db:
            return rows(db.execute('SELECT * FROM automation_runs ORDER BY executed_at DESC LIMIT 30'))

    @app.get('/api/alerts')
    def alerts(_=Depends(require_login)):
        with store.connection() as db:
            return rows(db.execute("SELECT * FROM alerts WHERE status='open' ORDER BY created_at DESC"))

    @app.post('/api/alerts/{ident}/dismiss')
    def dismiss(ident:str,_=Depends(require_login)):
        with store.transaction() as db:
            result=db.execute("UPDATE alerts SET status='dismissed',closed_at=? WHERE id=? AND status='open'",(now_utc(),ident))
            if not result.rowcount:
                raise HTTPException(404,'Alerta aberto não encontrado')
            record(db,'alert',ident,'dismiss')
        return {'ok':True}

    @app.get('/api/export')
    def export_owned_data(_=Depends(require_login)):
        allowed=('projects','contacts','opportunities','tasks','events','notes','meeting_transcripts','meeting_analyses','meeting_suggestions','automation_configs','automation_runs','alerts','audit')
        with store.connection() as db:
            result={'version':1,'generated_at':now_utc(),
                    'warning':'Contém informações privadas. Armazene em local protegido.'}
            for table in allowed:
                result[table]=rows(db.execute(f'SELECT * FROM {table}'))
        return JSONResponse(result,headers={'Content-Disposition':'attachment; filename="kelwin-hub-export.json"'})

    @app.get('/api/audit')
    def audit(_=Depends(require_login)):
        with store.connection() as db:
            return rows(db.execute('SELECT * FROM audit ORDER BY at DESC LIMIT 50'))

    from .meeting_review import register_meeting_review
    register_meeting_review(app,store,require_login,timestamp)
    from .availability import register_availability
    register_availability(app,store,require_login)
    return app

