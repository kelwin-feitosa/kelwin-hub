"""H17-03/13: more than 100 notes remain visible, addressable and editable."""
import pytest
from fastapi.testclient import TestClient
from hub.api import create_app
from hub.security import hash_password


def insert_note(client, headers, index, project_id=None):
    response=client.post('/api/notes',headers=headers,json={
        'title':f'Nota fictícia {index:03d}', 'body':f'Conteúdo da nota fictícia {index}',
        'project_id':project_id})
    assert response.status_code==201,response.text
    return response.json()['id']


def test_notes_pagination_stable_count_and_oldest_by_id(ctx):
    client, heads, store=ctx
    oldest=insert_note(client,heads,0)
    with store.transaction() as db:
        db.execute("UPDATE notes SET updated_at='2020-01-01T00:00:00+00:00' WHERE id=?",(oldest,))
    for i in range(1,121):
        insert_note(client,heads,i)
    seen=[]
    for offset in (0,30,60,90,120):
        result=client.get('/api/notes/page',params={'limit':30,'offset':offset})
        assert result.status_code==200,result.text
        payload=result.json()
        assert payload['total']==121
        assert payload['offset']==offset and payload['limit']==30
        assert len(payload['items'])==(1 if offset==120 else 30)
        assert payload['has_more']==(offset<120)
        seen.extend(row['id'] for row in payload['items'])
    assert len(set(seen))==121 and seen[-1]==oldest
    assert len(client.get('/api/notes').json())==100  # legacy shape and cap
    loaded=client.get('/api/notes/'+oldest)
    assert loaded.status_code==200
    assert loaded.json()['title']=='Nota fictícia 000'
    edited=client.patch('/api/notes/'+oldest,headers=heads,
                         json={'title':'Nota antiga editada','body':'Persistida corretamente'})
    assert edited.status_code==200,edited.text
    assert client.get('/api/notes/'+oldest).json()['title']=='Nota antiga editada'


def test_note_page_uses_exact_context_filter(ctx):
    client,heads,_=ctx
    project=client.post('/api/projects',headers=heads,json={'name':'Projeto A','area':'estudos'}).json()['id']
    note_id=insert_note(client,heads,1,project_id=project)
    insert_note(client,heads,2)
    filtered=client.get('/api/notes/page',params={'project_id':project,'limit':5}).json()
    assert filtered['total']==1 and filtered['items'][0]['id']==note_id
    assert filtered['has_more'] is False
    assert client.get('/api/notes/'+note_id).json()['project_id']==project


@pytest.mark.parametrize('query',[
    {'limit':0},{'limit':101},{'offset':-1},{'offset':100001},
    {'limit':'anything'},{'offset':'NaN'}
])
def test_notes_page_rejects_invalid_pagination(ctx,query):
    client,_,_=ctx
    response=client.get('/api/notes/page',params=query)
    assert response.status_code==422,response.text


def test_note_by_id_requires_auth_and_unknown_is_404(tmp_path):
    app=create_app(str(tmp_path/'notes.db'),
                   password_hash=hash_password('Synthetic-pass-2026'),
                   session_secret='S'*48,scheduler=False)
    with TestClient(app) as client:
        assert client.get('/api/notes/page').status_code==401
        assert client.get('/api/notes/nonexistent').status_code==401
        assert client.post('/api/login',json={'password':'Synthetic-pass-2026'}).status_code==200
        assert client.get('/api/notes/nonexistent').status_code==404
        assert client.get('/api/notes/page').json()['total']==0
