"""NEXO 14.0 suggestions: factual, private and human-controlled."""
from fastapi.testclient import TestClient
from hub.api import create_app
from hub.security import hash_password
from hub.meeting_review import digest


def test_suggestions_require_login(tmp_path):
    app=create_app(str(tmp_path/'db.db'),
       password_hash=hash_password('Senha-Ficticia-NEXO-2026'),
       session_secret='K'*48,scheduler=False)
    with TestClient(app) as client:
        assert client.get('/api/nexo/suggestions').status_code==401


def test_project_suggestion_is_read_only_and_explainable(ctx):
    c,h,store=ctx
    pid=c.post('/api/projects',headers=h,json={'name':'Projeto sem tarefas','area':'Teste'}).json()['id']
    with store.connection() as db:
        audit_before=db.execute('SELECT count(*) FROM audit').fetchone()[0]
    items=c.get('/api/nexo/suggestions').json()
    suggestion=next(x for x in items if x['id']==pid)
    assert suggestion['kind']=='project_next_step'
    assert suggestion['evidence']=={'status':'active','open_or_blocked_tasks':0}
    assert len(items)<=3
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM audit').fetchone()[0]==audit_before
    task=c.post('/api/tasks',headers=h,json={'title':'Próximo passo','project_id':pid}).json()['id']
    assert pid not in {x['id'] for x in c.get('/api/nexo/suggestions').json()}
    assert c.patch('/api/tasks/'+task,headers=h,json={'status':'done'}).status_code==200
    assert pid in {x['id'] for x in c.get('/api/nexo/suggestions').json()}


def test_meeting_suggestions_require_human_review(ctx):
    c,h,store=ctx
    event=c.post('/api/events',headers=h,json={'title':'Reunião fictícia','status':'proposed',
      'start_at':'2027-02-20T12:00:00Z','end_at':'2027-02-20T13:00:00Z'}).json()['id']
    content='Concluímos a reunião. Ainda precisamos enviar o relatório.'
    tid=c.post('/api/events/'+event+'/transcripts',headers=h,
      json={'format':'txt','content':content,'source_name':'ficticio.txt'}).json()['id']
    payload={'schema_version':1,'transcript_id':tid,'transcript_hash':digest(content),
      'items':[{'kind':'action','title':'Enviar relatório',
        'evidence':{'quote':'Ainda precisamos enviar o relatório.'}}]}
    result=c.post('/api/meeting-review/transcripts/'+tid+'/analyses',headers=h,json=payload)
    assert result.status_code==201,result.text
    suggestions=c.get('/api/nexo/suggestions').json()
    review=next(x for x in suggestions if x['kind']=='meeting_review')
    assert review['id']==tid and review['evidence']['pending_items']==1
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]==0
    item=c.get('/api/meeting-review/transcripts/'+tid+'/analyses').json()[0]['items'][0]['id']
    converted=c.post('/api/meeting-review/items/'+item+'/convert',headers=h,json={'title':'Enviar relatório'})
    assert converted.status_code==200
    assert tid not in {x['id'] for x in c.get('/api/nexo/suggestions').json()}
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]==1