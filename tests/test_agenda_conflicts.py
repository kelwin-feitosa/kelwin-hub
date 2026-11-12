"""Time-zone correct, transactionally serialized booking conflicts and contextual events."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from hub.api import create_app
from hub.storage import Store


def payload(title='Primeiro',start='2026-11-13T15:00',end='2026-11-13T15:30',status='confirmed',**extra):
    return {'title':title,'start_at':start,'end_at':end,'status':status,**extra}


def test_conflict_boundary_cancel_proposed_and_shift(ctx):
    c,h,_=ctx
    first=c.post('/api/events',headers=h,json=payload()).json()['id']
    assert c.post('/api/events',headers=h,json=payload('Choque','2026-11-13T15:15','2026-11-13T16:00')).status_code==409
    assert c.get('/api/events/conflicts',params={'start_at':'2026-11-13T15:15','end_at':'2026-11-13T16:00'}).json()['available'] is False
    assert c.get('/api/events/conflicts',params={'start_at':'2026-11-13T15:30','end_at':'2026-11-13T16:00'}).json()['available'] is True
    assert c.post('/api/events',headers=h,json=payload('Adjacente','2026-11-13T15:30','2026-11-13T16:00')).status_code==201
    proposed=c.post('/api/events',headers=h,json=payload('Proposta','2026-11-13T15:15','2026-11-13T16:00','proposed')).json()['id']
    assert c.patch('/api/events/'+proposed,headers=h,json={'status':'confirmed'}).status_code==409
    assert c.patch('/api/events/'+first,headers=h,json={'status':'cancelled'}).status_code==200
    assert c.patch('/api/events/'+proposed,headers=h,json={'status':'confirmed'}).status_code==409 # still conflicts with Adjacente
    assert c.patch('/api/events/'+proposed,headers=h,json={'end_at':'2026-11-13T15:30','status':'confirmed'}).status_code==200
    assert c.patch('/api/events/'+proposed,headers=h,json={'end_at':'2026-11-13T15:00'}).status_code==422
    assert c.patch('/api/events/'+proposed,headers=h,json={'title':'Atualizado'}).status_code==200
    assert c.get('/api/events/conflicts',params={'start_at':'2026-11-13T15:15','end_at':'2026-11-13T15:30','ignore_id':proposed}).json()['available'] is True


def test_project_contact_relationship_and_local_timezone(ctx):
    c,h,_=ctx
    pid=c.post('/api/projects',headers=h,json={'name':'Projeto'}).json()['id']
    cid=c.post('/api/contacts',headers=h,json={'name':'Pessoa'}).json()['id']
    event=c.post('/api/events',headers=h,json=payload(project_id=pid,contact_id=cid))
    assert event.status_code==201
    ident=event.json()['id']
    item=next(x for x in c.get('/api/events').json() if x['id']==ident)
    assert item['start_at']=='2026-11-13T18:00:00+00:00'
    assert item['project_id']==pid and item['contact_id']==cid
    act=c.get('/api/activity',params={'kind':'project','ident':pid}).json()
    assert any(x['kind']=='event' and x['entity_id']==ident for x in act)
    assert c.post('/api/events',headers=h,json=payload('Invalido',project_id='missing')).status_code==404
    assert c.get('/api/events/conflicts',params={'start_at':'2026-11-13T16:00','end_at':'2026-11-13T15:00'}).status_code==422
    assert c.get('/api/events/conflicts',params={'start_at':'x','end_at':'2026-11-13T15:00'}).status_code==422
    assert c.patch('/api/events/'+ident,headers=h,json={'contact_id':'missing'}).status_code==404
    assert c.post('/api/events',json=payload('Sem token')).status_code==403


def test_UTC_equivalent_times_overlapping_and_proposed_does_not_block(ctx):
    c,h,_=ctx
    c.post('/api/events',headers=h,json=payload())
    assert c.post('/api/events',headers=h,json=payload('UTC','2026-11-13T18:05:00Z','2026-11-13T18:20:00+00:00')).status_code==409
    assert c.post('/api/events',headers=h,json=payload('Proposto','2026-11-13T18:05:00Z','2026-11-13T18:20:00Z','proposed')).status_code==201


def test_concurrent_confirmed_reservations_one_winner(ctx):
    c,h,store=ctx
    # TestClient's cookie/headers are shared but no mutations; transactional BEGIN IMMEDIATE in SQLite is the gate.
    def reserve(_):
        return c.post('/api/events',headers=h,json=payload(f'Tentativa {_}')).status_code
    with ThreadPoolExecutor(max_workers=5) as pool:
        statuses=list(pool.map(reserve,range(5)))
    assert statuses.count(201)==1 and statuses.count(409)==4
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM events WHERE status='confirmed'").fetchone()[0]==1


def test_null_edit_end_date_is_422_not_500(ctx):
    c,h,_=ctx
    event=c.post('/api/events',headers=h,json=payload()).json()['id']
    assert c.patch('/api/events/'+event,headers=h,json={'start_at':None}).status_code==422
    assert c.patch('/api/events/'+event,headers=h,json={'end_at':None}).status_code==422
    assert c.patch('/api/events/'+event,headers=h,json={'status':None}).status_code==422


def test_upgrade_v2_to_v3_preserves_notes(tmp_path):
    from pathlib import Path
    from hub.storage import SCHEMA, MIGRATIONS, LATEST_SCHEMA_VERSION
    path=tmp_path/'v2.db'
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        for version,file in [(1,'001_sessions_scheduler_integrity.sql'),(2,'002_notes_context.sql')]:
            script=(MIGRATIONS/file).read_text()
            db.executescript(f'BEGIN IMMEDIATE;\n{script}\nPRAGMA user_version={version};\nCOMMIT;')
        db.execute('INSERT INTO projects VALUES (?,?,?,?,?)', ('pid','Projeto','pessoal','active','2026-11-11'))
        db.execute('INSERT INTO notes VALUES (?,?,?,?,?,?,?,?)', ('nid','Nota','Texto','pid',None,None,'2026-11-11','2026-11-11'))
        db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?)', ('eid','Antigo','2026-11-11T11:00:00+00:00','2026-11-11T11:30:00+00:00','confirmed','local','2026-11-11'))
    Store(str(path))
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==LATEST_SCHEMA_VERSION
        assert db.execute('SELECT title FROM notes WHERE id="nid"').fetchone()[0]=='Nota'
        assert db.execute('SELECT title,project_id FROM events WHERE id="eid"').fetchone()==('Antigo',None)
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
