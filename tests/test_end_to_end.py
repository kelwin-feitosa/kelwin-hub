from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from fastapi.testclient import TestClient
from hub.api import create_app
from hub.security import hash_password
from hub.automation import run_stale
from hub.storage import now_utc


def make_contact(client,heads,email='ana@example.test'):
    r=client.post('/api/contacts',headers=heads,json={'name':'Ana Exemplo','company':'Teste','email':email})
    assert r.status_code==201,r.text
    return r.json()['id']


def make_opp(client,heads,cid):
    r=client.post('/api/opportunities',headers=heads,json={
        'contact_id':cid,'title':'Orçamento de site','kind':'service',
        'next_action':'Enviar proposta','value_brl':'1250.50','followup_at':'2026-11-12T13:30'})
    assert r.status_code==201,r.text
    return r.json()['id']


def test_login_and_logout(tmp_path):
    app=create_app(str(tmp_path/'a.db'),password_hash=hash_password('A-senha-ficticia-forte'),session_secret='S'*48,scheduler=False)
    with TestClient(app) as client:
        assert client.get('/api/projects').status_code==401
        assert client.post('/api/login',json={'password':'incorrect'}).status_code==401
        assert client.post('/api/login',json={'password':'A-senha-ficticia-forte'}).status_code==200
        csrf=client.get('/api/session').json()['csrf']
        assert client.get('/api/projects').status_code==200
        assert client.post('/api/logout',headers={'X-CSRF-Token':csrf},json={}).status_code==200
        assert client.get('/api/projects').status_code==401


def test_csrf_and_origin(ctx):
    client,heads,_=ctx
    assert client.post('/api/projects',json={'name':'A'}).status_code==403
    assert client.post('/api/projects',headers={'X-CSRF-Token':'wrong'},json={'name':'A'}).status_code==403
    assert client.post('/api/projects',headers={**heads,'Origin':'https://evil.example'},json={'name':'A'}).status_code==403
    assert client.get('/api/projects').status_code==200


def test_complete_journey(ctx):
    client,heads,store=ctx
    r=client.post('/api/projects',headers=heads,json={'name':'Sites de clientes','area':'Trabalho'})
    assert r.status_code==201
    project=r.json()['id']
    cid=make_contact(client,heads)
    opp=make_opp(client,heads,cid)
    task=client.post('/api/tasks',headers=heads,json={'title':'Preparar proposta','project_id':project,'opportunity_id':opp,'priority':2,'due_at':'2026-11-12T14:00'})
    assert task.status_code==201
    dash=client.get('/api/dashboard').json()
    assert dash['totals']['projects']==1 and dash['totals']['opportunities']==1
    assert any(x['title']=='Preparar proposta' for x in dash['tasks'])
    task_id=task.json()['id']
    assert client.patch(f'/api/tasks/{task_id}',headers=heads,json={'status':'done'}).status_code==200
    assert client.get('/api/dashboard').json()['totals']['tasks']==0
    assert len(client.get('/api/audit').json())==5


def test_contact_duplicate_and_normalization(ctx):
    c,h,_=ctx
    make_contact(c,h)
    r=c.post('/api/contacts',headers=h,json={'name':'Outro','email':' ANA@EXAMPLE.TEST '})
    assert r.status_code==409
    assert len(c.get('/api/contacts').json())==1


def test_invalid_data(ctx):
    c,h,_=ctx
    assert c.post('/api/contacts',headers=h,json={'name':'Ana','email':'bad@@email'}).status_code==422
    assert c.post('/api/contacts',headers=h,json={'name':'Ana','extra':'invalid'}).status_code==422
    assert c.post('/api/opportunities',headers=h,json={'contact_id':'missing','title':'X','next_action':'Y'}).status_code==404
    cid=make_contact(c,h)
    req={'contact_id':cid,'title':'Site','next_action':'Ligar','value_brl':'-1'}
    assert c.post('/api/opportunities',headers=h,json=req).status_code==422
    req['value_brl']='0.001'
    assert c.post('/api/opportunities',headers=h,json=req).status_code==422
    assert c.post('/api/tasks',headers=h,json={'title':'T','project_id':'missing'}).status_code==404
    assert c.post('/api/tasks',headers=h,json={'title':'T','priority':7}).status_code==422


def test_events_and_date_logic(ctx):
    c,h,_=ctx
    r=c.post('/api/events',headers=h,json={'title':'Reunião proposta','start_at':'2026-11-12T09:00','end_at':'2026-11-12T10:00','status':'proposed'})
    assert r.status_code==201
    evt=c.get('/api/events').json()[0]
    assert evt['start_at']=='2026-11-12T12:00:00+00:00'
    assert evt['status']=='proposed'
    assert c.post('/api/events',headers=h,json={'title':'X','start_at':'2026-11-12T11:00','end_at':'2026-11-12T10:00'}).status_code==422
    assert c.post('/api/events',headers=h,json={'title':'X','start_at':'invalid','end_at':'2026-11-12T10:00'}).status_code==422


def test_automation_detects_and_deduplicates(ctx):
    c,h,store=ctx
    opp=make_opp(c,h,make_contact(c,h))
    old=(datetime.now(timezone.utc)-timedelta(days=12)).isoformat(timespec='seconds')
    with store.transaction() as db:
        db.execute('UPDATE opportunities SET created_at=? WHERE id=?',(old,opp))
    first=c.post('/api/automations/stale_opportunities/run',headers=h,json={})
    assert first.json()['created']==1
    second=c.post('/api/automations/stale_opportunities/run',headers=h,json={})
    assert second.json()['created']==0
    assert c.get('/api/dashboard').json()['totals']['alerts']==1
    assert len(c.get('/api/automation-runs').json())==2
    assert c.post(f'/api/opportunities/{opp}/contact',headers=h,json={}).status_code==200
    assert c.get('/api/dashboard').json()['totals']['alerts']==0


def test_automation_threshold_and_disable(ctx):
    c,h,store=ctx
    opp=make_opp(c,h,make_contact(c,h))
    with store.transaction() as db:
        db.execute('UPDATE opportunities SET created_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(days=7)).isoformat(timespec='seconds'),opp))
    assert c.patch('/api/automations/stale_opportunities',headers=h,json={'enabled':True,'threshold_days':8}).status_code==200
    assert c.post('/api/automations/stale_opportunities/run',headers=h,json={}).json()['created']==0
    assert c.patch('/api/automations/stale_opportunities',headers=h,json={'enabled':True,'threshold_days':5}).status_code==200
    assert c.post('/api/automations/stale_opportunities/run',headers=h,json={}).json()['created']==1
    assert c.patch('/api/automations/stale_opportunities',headers=h,json={'enabled':False,'threshold_days':5}).status_code==200
    assert c.post('/api/automations/stale_opportunities/run',headers=h,json={}).json()['executed'] is False


def test_internal_token(ctx):
    c,h,store=ctx
    route='/api/internal/automations/stale_opportunities/run'
    assert c.post(route,json={}).status_code==401
    assert c.post(route,headers={'X-Hub-Internal-Token':'incorrect'},json={}).status_code==401
    assert c.post(route,headers={'X-Hub-Internal-Token':'internal-token-test-001'},json={}).status_code==200


def test_dismiss_alert(ctx):
    c,h,store=ctx
    ident='test-alert'
    with store.transaction() as db:
        db.execute("INSERT INTO alerts VALUES (?,?,?,?,'open',?,NULL)",(ident,'stale_opportunities','some-id','Alert demo',now_utc()))
    assert c.post('/api/alerts/test-alert/dismiss',headers=h,json={}).status_code==200
    assert c.post('/api/alerts/test-alert/dismiss',headers=h,json={}).status_code==404


def test_data_persists(tmp_path):
    path=str(tmp_path/'persistent.db')
    config={'password_hash':hash_password('Senha-ficticia-1234'),'session_secret':'S'*48,'scheduler':False}
    with TestClient(create_app(path,**config)) as c:
        c.post('/api/login',json={'password':'Senha-ficticia-1234'})
        h={'X-CSRF-Token':c.get('/api/session').json()['csrf']}
        c.post('/api/projects',headers=h,json={'name':'Projeto persistente'})
    with TestClient(create_app(path,**config)) as c:
        c.post('/api/login',json={'password':'Senha-ficticia-1234'})
        assert len(c.get('/api/projects').json())==1


def test_invalid_task_state_and_missing_contact(ctx):
    c,h,_=ctx
    assert c.patch('/api/tasks/missing',headers=h,json={'status':'done'}).status_code==404
    task=c.post('/api/tasks',headers=h,json={'title':'Teste'}).json()['id']
    assert c.patch('/api/tasks/'+task,headers=h,json={'status':'invalid'}).status_code==422
    assert c.post('/api/opportunities/missing/contact',headers=h,json={}).status_code==404


def test_static_works(ctx):
    c,h,_=ctx
    assert c.get('/').status_code==200
    assert c.get('/static/app.js').status_code==200
    assert c.get('/healthz').json()['status']=='ok'
    assert c.get('/').headers.get('Content-Security-Policy','').startswith('default-src')


def test_concurrent_automation_dedup(ctx):
    c,h,store=ctx
    opp=make_opp(c,h,make_contact(c,h))
    with store.transaction() as db:
        db.execute('UPDATE opportunities SET created_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(days=50)).isoformat(timespec='seconds'),opp))
    with ThreadPoolExecutor(max_workers=4) as ex:
        results=list(ex.map(lambda _:run_stale(store),range(4)))
    assert sum(x['created'] for x in results)==1
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM alerts WHERE status='open'").fetchone()[0]==1


def test_edit_and_archive_project(ctx):
    c,h,_=ctx
    ident=c.post('/api/projects',headers=h,json={'name':'Antigo','area':'pessoal'}).json()['id']
    assert c.patch('/api/projects/'+ident,headers=h,json={'name':'Novo','status':'paused'}).status_code==200
    assert c.get('/api/projects').json()[0]['name']=='Novo'
    assert c.get('/api/projects').json()[0]['status']=='paused'
    assert c.patch('/api/projects/'+ident,headers=h,json={'status':'unknown'}).status_code==422
    assert c.patch('/api/projects/'+ident,headers=h,json={'name':'  '}).status_code==422


def test_edit_contact_dedup(ctx):
    c,h,_=ctx
    first=make_contact(c,h)
    second=make_contact(c,h,email='outro@example.test')
    assert c.patch('/api/contacts/'+second,headers=h,json={'email':'ana@example.test'}).status_code==409
    assert c.patch('/api/contacts/'+second,headers=h,json={'email':'outro+alterado@example.test','name':'Novo nome'}).status_code==200
    assert next(x for x in c.get('/api/contacts').json() if x['id']==second)['name']=='Novo nome'


def test_edit_opportunity_status_resolves_alert(ctx):
    c,h,store=ctx
    opp=make_opp(c,h,make_contact(c,h))
    with store.transaction() as db:
        db.execute('UPDATE opportunities SET created_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(days=20)).isoformat(timespec='seconds'),opp))
    c.post('/api/automations/stale_opportunities/run',headers=h,json={})
    assert len(c.get('/api/alerts').json())==1
    assert c.patch('/api/opportunities/'+opp,headers=h,json={'status':'won','next_action':'Encerrada'}).status_code==200
    assert len(c.get('/api/alerts').json())==0
    assert c.patch('/api/opportunities/'+opp,headers=h,json={'status':'impossible'}).status_code==422


def test_edit_task_and_event(ctx):
    c,h,_=ctx
    task=c.post('/api/tasks',headers=h,json={'title':'Tarefa inicial'}).json()['id']
    assert c.patch('/api/tasks/'+task,headers=h,json={'title':'Tarefa editada','priority':3}).status_code==200
    assert c.get('/api/tasks').json()[0]['priority']==3
    event=c.post('/api/events',headers=h,json={'title':'Proposta','start_at':'2026-11-12T09:00','end_at':'2026-11-12T10:00','status':'proposed'}).json()['id']
    assert c.patch('/api/events/'+event,headers=h,json={'status':'confirmed'}).status_code==200
    assert c.get('/api/events').json()[0]['status']=='confirmed'
    assert c.patch('/api/events/'+event,headers=h,json={'status':'invalid'}).status_code==422


def test_dismissal_silences_episode_until_new_contact(ctx):
    c,h,store=ctx
    op=make_opp(c,h,make_contact(c,h))
    old=(datetime.now(timezone.utc)-timedelta(days=15)).isoformat(timespec='seconds')
    with store.transaction() as db: db.execute('UPDATE opportunities SET created_at=? WHERE id=?',(old,op))
    c.post('/api/automations/stale_opportunities/run',headers=h,json={})
    alert=c.get('/api/alerts').json()[0]
    c.post(f"/api/alerts/{alert['id']}/dismiss",headers=h,json={})
    assert c.post('/api/automations/stale_opportunities/run',headers=h,json={}).json()['created']==0
    c.post(f'/api/opportunities/{op}/contact',headers=h,json={})
    with store.transaction() as db:
        db.execute('UPDATE opportunities SET last_contact_at=? WHERE id=?',(old,op))
    assert c.post('/api/automations/stale_opportunities/run',headers=h,json={}).json()['created']==0  # older than dismissal, still silenced


def test_failed_automation_writes_failure_log(tmp_path, monkeypatch):
    from hub import automation as a
    store=__import__('hub.storage',fromlist=['Store']).Store(str(tmp_path/'failed.db'))
    def boom(*args,**kwargs):raise RuntimeError('sensitive info not for logs')
    monkeypatch.setattr(a,'run_stale',boom)
    with pytest.raises(RuntimeError):a.safe_run_stale(store)
    with store.connection() as db:
        rec=db.execute('SELECT status,error FROM automation_runs').fetchone()
        assert rec['status']=='failed' and rec['error']=='RuntimeError'


def test_private_export_and_content(ctx):
    c,h,_=ctx
    make_contact(c,h)
    r=c.get('/api/export')
    assert r.status_code==200
    doc=r.json()
    assert doc['version']==1 and len(doc['contacts'])==1 and 'automation_configs' in doc
    assert 'attachment' in r.headers['Content-Disposition']

@pytest.mark.parametrize('invalid', [
    '-1', '1.234', '1e100000000', 'NaN', 'Infinity',
    '99999999999', ' ' + '9' * 1000, '1,50',
])
def test_untrusted_money_is_bounded_and_rejected(ctx, invalid):
    client, heads, store = ctx
    cid = make_contact(client, heads)
    request = {'contact_id': cid, 'title': 'Teste de validação',
               'next_action': 'Revisar', 'value_brl': invalid}
    result = client.post('/api/opportunities', headers=heads, json=request)
    assert result.status_code == 422, result.text
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0] == 0


@pytest.mark.parametrize(('value', 'expected_cents'), [
    ('0', 0), ('12.3', 1230), ('1250.50', 125050), ('9999999999.99', 999999999999),
])
def test_crm_money_preserves_valid_decimal_amounts(ctx, value, expected_cents):
    client, heads, store = ctx
    cid = make_contact(client, heads)
    request = {'contact_id': cid, 'title': 'Valor legítimo',
               'next_action': 'Acompanhar', 'value_brl': value}
    result = client.post('/api/opportunities', headers=heads, json=request)
    assert result.status_code == 201, result.text
    with store.connection() as db:
        actual = db.execute('SELECT value_cents FROM opportunities WHERE id=?',
                            (result.json()['id'],)).fetchone()[0]
    assert actual == expected_cents
