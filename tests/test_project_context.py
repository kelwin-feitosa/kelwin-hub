"""Project contextual view: same entities, read only, no extra table."""


def test_project_context_requires_login(tmp_path):
    from fastapi.testclient import TestClient
    from hub.api import create_app
    from hub.security import hash_password
    app=create_app(str(tmp_path/'hub.db'),password_hash=hash_password('fake-password-with-length'),
                   session_secret='unit-test-secret-'*4,scheduler=False)
    with TestClient(app) as client:
        assert client.get('/api/projects/not-found/context').status_code==401


def test_project_context_only_includes_related_tasks_and_counts(ctx):
    client,csrf,store=ctx
    first=client.post('/api/projects',headers=csrf,json={'name':'Projeto da Flauta','area':'música'}).json()['id']
    other=client.post('/api/projects',headers=csrf,json={'name':'Projeto API','area':'código'}).json()['id']
    task_a=client.post('/api/tasks',headers=csrf,json={'title':'Revisar dinâmica','project_id':first,'priority':3}).json()['id']
    task_b=client.post('/api/tasks',headers=csrf,json={'title':'Preparar articulação','project_id':first}).json()['id']
    client.post('/api/tasks',headers=csrf,json={'title':'Testes da API','project_id':other})
    client.patch('/api/tasks/'+task_b,headers=csrf,json={'status':'blocked'})
    with store.connection() as db:
        audited_before=db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
    response=client.get('/api/projects/'+first+'/context')
    assert response.status_code==200
    result=response.json()
    assert result['project']['name']=='Projeto da Flauta'
    assert result['counts']=={'open':1,'blocked':1,'done':0}
    assert result['next_task']['id']==task_a
    assert {t['id'] for t in result['tasks']}=={task_a,task_b}
    assert result['recent_activity']
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]==audited_before
    assert client.get('/api/projects/'+other+'/context').json()['counts']['open']==1
    assert client.get('/api/projects/missing/context').status_code==404


def test_project_task_completion_updates_context_without_finishing_project(ctx):
    client,csrf,_=ctx
    pid=client.post('/api/projects',headers=csrf,json={'name':'Trabalho Pessoal','area':'pessoal'}).json()['id']
    tid=client.post('/api/tasks',headers=csrf,json={'title':'Concluir introdução','project_id':pid}).json()['id']
    assert client.patch('/api/tasks/'+tid,headers=csrf,json={'status':'done'}).status_code==200
    result=client.get('/api/projects/'+pid+'/context').json()
    assert result['counts']=={'open':0,'blocked':0,'done':1}
    assert result['next_task'] is None
    assert result['project']['status']=='active'


def test_contextual_project_ui_is_integrated():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[1]/'hub/static/app.js').read_text()
    assert "async function showProjectContext(id)" in text
    assert '/context' in text
    assert "case'add-project-task'" in text
    assert "value:projectId||''" in text
    assert 'aria-expanded="false"' in text
