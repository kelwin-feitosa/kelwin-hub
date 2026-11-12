"""New notes and contextual audit views retain foreign keys, authentication, and user data."""
import sqlite3
from fastapi.testclient import TestClient
from hub.api import create_app
from hub.security import hash_password
from hub.storage import LATEST_SCHEMA_VERSION, Store


def test_notes_context_search_and_activity(ctx):
    c, csrf, _ = ctx
    project=c.post('/api/projects',headers=csrf,json={'name':'Projeto musical'}).json()['id']
    contact=c.post('/api/contacts',headers=csrf,json={'name':'Pessoa fictícia'}).json()['id']
    opp=c.post('/api/opportunities',headers=csrf,json={'contact_id':contact,'title':'Proposta','next_action':'Responder'}).json()['id']
    task=c.post('/api/tasks',headers=csrf,json={'title':'Conferir pauta','project_id':project}).json()['id']
    note=c.post('/api/notes',headers=csrf,json={'title':'Reunião inicial','body':'Acordes e próximos passos <script>alert(1)</script>',
                   'project_id':project,'opportunity_id':opp,'contact_id':contact})
    assert note.status_code==201
    nid=note.json()['id']
    found=c.get('/api/notes',params={'project_id':project}).json()
    assert len(found)==1 and found[0]['id']==nid
    assert found[0]['body'].startswith('Acordes')
    assert c.get('/api/notes',params={'project_id':'x'}).json()==[]
    assert (nid,'notes') in {(i['id'],i['kind']) for i in c.get('/api/search',params={'q':'acordes'}).json()['results']}
    assert (nid,'notes') in {(i['id'],i['kind']) for i in c.get('/api/search',params={'q':'proposta'}).json()['results']}
    assert c.patch('/api/notes/'+nid,headers=csrf,json={'body':'Novo conteúdo'}).status_code==200
    assert c.get('/api/notes').json()[0]['body']=='Novo conteúdo'
    assert c.get('/api/activity',params={'kind':'project','ident':project}).status_code==200
    project_actions=c.get('/api/activity',params={'kind':'project','ident':project}).json()
    assert ('task',task,'create') in {(i['kind'],i['entity_id'],i['action']) for i in project_actions}
    assert ('note',nid,'update') in {(i['kind'],i['entity_id'],i['action']) for i in project_actions}
    opp_actions=c.get('/api/activity',params={'kind':'opportunity','ident':opp}).json()
    assert ('note',nid,'create') in {(i['kind'],i['entity_id'],i['action']) for i in opp_actions}
    assert len(c.get('/api/activity',params={'kind':'project','ident':project,'limit':1,'offset':1}).json())==1
    assert c.get('/api/export').json()['notes'][0]['id']==nid


def test_notes_validation_and_security(ctx):
    c,csrf,_=ctx
    assert c.get('/api/notes').status_code==200
    assert c.get('/api/notes',params={'limit':1000}).status_code==422
    assert c.get('/api/activity',params={'kind':'unknown','ident':'whatever'}).status_code==422
    assert c.get('/api/activity',params={'kind':'project','ident':'missing'}).status_code==404
    assert c.post('/api/notes',json={'title':'X','body':'Y'}).status_code==403
    assert c.post('/api/notes',headers=csrf,json={'title':'X','body':'Y','project_id':'missing'}).status_code==404
    for title,body in [(' ','ok'),('ok','  ')]:
        assert c.post('/api/notes',headers=csrf,json={'title':title,'body':body}).status_code==422
    nid=c.post('/api/notes',headers=csrf,json={'title':'Teste','body':'Texto'}).json()['id']
    assert c.patch('/api/notes/'+nid,headers=csrf,json={'body':''}).status_code==422
    assert c.patch('/api/notes/'+nid,headers=csrf,json={'project_id':'x'}).status_code==422
    assert c.patch('/api/notes/absent',headers=csrf,json={'body':'Valid'}).status_code==404


def test_migration_from_original_11_preserves_existing_records(tmp_path):
    path=str(tmp_path/'old.db')
    Store(path)
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO projects VALUES (?,?,?,?,?)', ('saved','Mantido','pessoal','active','2026-01-01'))
        db.execute('DROP TABLE notes')
        db.execute('DROP INDEX IF EXISTS notes_updated_idx')
        db.execute('DROP INDEX IF EXISTS notes_project_idx')
        db.execute('DROP INDEX IF EXISTS notes_contact_idx')
        db.execute('DROP INDEX IF EXISTS notes_opportunity_idx')
        db.execute('DROP INDEX IF EXISTS audit_lookup_idx')
        db.execute('PRAGMA user_version=1')
    Store(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==LATEST_SCHEMA_VERSION
        assert db.execute('SELECT name FROM projects WHERE id=?',('saved',)).fetchone()[0]=='Mantido'
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert db.execute('SELECT COUNT(*) FROM notes').fetchone()[0]==0
