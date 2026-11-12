"""NEXO: contextual projections must be read-only, isolated and authenticated."""
from fastapi.testclient import TestClient
from hub.api import create_app
from hub.security import hash_password


def test_context_requires_session(tmp_path):
    app = create_app(str(tmp_path/'hub.db'),
                     password_hash=hash_password('Senha-Contexto-NEXO-2026'),
                     session_secret='context-secret-'*4,scheduler=False)
    with TestClient(app) as c:
        assert c.get('/api/opportunities/id/context').status_code == 401


def test_project_context_embeds_only_its_notes_and_events(ctx):
    c,csrf,store=ctx
    a=c.post('/api/projects',headers=csrf,json={'name':'Projeto A','area':'Teste'}).json()['id']
    b=c.post('/api/projects',headers=csrf,json={'name':'Projeto B','area':'Teste'}).json()['id']
    c.post('/api/notes',headers=csrf,json={'title':'Anotação A','body':'Conteúdo <script>teste</script>','project_id':a})
    c.post('/api/notes',headers=csrf,json={'title':'Anotação B','body':'Privado','project_id':b})
    c.post('/api/events',headers=csrf,json={'title':'Reunião A','project_id':a,'status':'proposed',
      'start_at':'2026-12-18T10:00:00Z','end_at':'2026-12-18T11:00:00Z'})
    with store.connection() as db:
        before=db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
    data=c.get('/api/projects/'+a+'/context').json()
    assert [x['title'] for x in data['notes']]==['Anotação A']
    assert [x['title'] for x in data['events']]==['Reunião A']
    assert '<script>' in data['notes'][0]['body']
    assert c.get('/api/projects/'+b+'/context').json()['events']==[]
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]==before


def test_opportunity_context_no_false_links_or_side_effects(ctx):
    c,csrf,store=ctx
    contact=c.post('/api/contacts',headers=csrf,json={'name':'Contato Fictício'}).json()['id']
    a=c.post('/api/opportunities',headers=csrf,json={'contact_id':contact,
       'title':'Oportunidade A','next_action':'Telefonar'}).json()['id']
    b=c.post('/api/opportunities',headers=csrf,json={'contact_id':contact,
       'title':'Oportunidade B','next_action':'Enviar proposta'}).json()['id']
    task=c.post('/api/tasks',headers=csrf,json={'title':'Retorno A','opportunity_id':a}).json()['id']
    c.post('/api/tasks',headers=csrf,json={'title':'Retorno B','opportunity_id':b})
    c.post('/api/notes',headers=csrf,json={'title':'Nota A','body':'Dados válidos','opportunity_id':a})
    c.post('/api/events',headers=csrf,json={'title':'Reunião do contato',
      'contact_id':contact,'status':'proposed','start_at':'2026-12-18T14:00:00Z','end_at':'2026-12-18T15:00:00Z'})
    with store.connection() as db:
        before=db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
    response=c.get('/api/opportunities/'+a+'/context')
    assert response.status_code==200
    data=response.json()
    assert data['opportunity']['contact_name']=='Contato Fictício'
    assert data['counts']=={'open':1,'blocked':0,'done':0}
    assert data['next_task']['id']==task
    assert [x['title'] for x in data['notes']]==['Nota A']
    assert 'events' not in data  # Contact events cannot be attributed to one opportunity
    assert all(t['title']!='Retorno B' for t in data['tasks'])
    assert c.get('/api/opportunities/'+b+'/context').json()['notes']==[]
    assert c.get('/api/opportunities/missing/context').status_code==404
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]==before
    assert c.patch('/api/tasks/'+task,headers=csrf,json={'status':'done'}).status_code==200
    assert c.get('/api/opportunities/'+a+'/context').json()['counts']['done']==1


def test_existing_indexes_support_contexts(ctx):
    _,_,store=ctx
    with store.connection() as db:
        statements=(
          "SELECT id FROM notes WHERE project_id='x' ORDER BY updated_at DESC LIMIT 8",
          "SELECT id FROM notes WHERE opportunity_id='x' ORDER BY updated_at DESC LIMIT 8",
          "SELECT id FROM events WHERE project_id='x' ORDER BY start_at DESC LIMIT 5"
        )
        for sql in statements:
            detail=' '.join(x['detail'] for x in db.execute('EXPLAIN QUERY PLAN '+sql))
            assert 'USING INDEX' in detail or 'USING COVERING INDEX' in detail, detail
