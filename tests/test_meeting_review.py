"""Synthetic end-to-end HTTP tests for human-controlled meeting review."""
import copy
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from hub.api import create_app
from hub.security import hash_password
from hub.meeting_review import digest


def setup(tmp_path):
    app = create_app(str(tmp_path/'review.db'),password_hash=hash_password('Fictional-password-1234'),session_secret='A'*48,scheduler=False)
    store = app.state.store
    with store.transaction() as db:
        db.execute("INSERT INTO events(id,title,start_at,end_at,status,created_at) VALUES('event1','Encontro de teste','2026-11-12T16:00:00+00:00','2026-11-12T17:00:00+00:00','confirmed','2026-11-12T12:00:00+00:00')")
        content='Ana sugeriu enviar proposta. Bruno confirmou: enviar proposta até sexta.\\nPrecisamos revisar orçamento.'
        db.execute("INSERT INTO meeting_transcripts(id,event_id,format,source_name,content,created_at) VALUES('trans1','event1','txt','ficcao.txt',?,'2026-11-12T17:00:00+00:00')",(content,))
    client=TestClient(app)
    assert client.post('/api/login',json={'password':'Fictional-password-1234'}).status_code==200
    heads={'X-CSRF-Token':client.get('/api/session').json()['csrf']}
    return client,heads,store,content


def analysis(text):
    quote='Bruno confirmou: enviar proposta até sexta.'
    start=text.index(quote)
    return {'schema_version':1,'transcript_id':'trans1','transcript_hash':digest(text),'summary':'A proposta será enviada.',
     'items':[{'kind':'action','title':'Enviar proposta','detail':'Confirmado pelo Bruno','suggested_due_at':None,
       'evidence':{'start':start,'end':start+len(quote),'quote':quote}}]}


def test_flow_auth_evidence_dedup_and_approval(tmp_path):
    c,h,store,text=setup(tmp_path)
    package=c.get('/api/meeting-review/transcripts/trans1/package')
    assert package.status_code==200 and package.json()['transcript']['content']==text
    assert 'ChatGPT' in package.json()['privacy_notice']
    good=analysis(text)
    endpoint='/api/meeting-review/transcripts/trans1/analyses'
    assert c.post(endpoint,json=good).status_code==403
    assert c.post(endpoint,headers={'x-csrf-token':'invalid'},json=good).status_code==403
    assert c.post(endpoint,headers={**h,'Origin':'https://malicious.example'},json=good).status_code==403
    bad=copy.deepcopy(good);bad['items'][0]['evidence']['quote']='texto inventado'
    assert c.post(endpoint,headers=h,json=bad).status_code==422
    bad=copy.deepcopy(good);bad['transcript_hash']='0'*64
    assert c.post(endpoint,headers=h,json=bad).status_code==409
    bad=copy.deepcopy(good);bad['items'][0]['approved']=True
    assert c.post(endpoint,headers=h,json=bad).status_code==422
    r=c.post(endpoint,headers=h,json=good)
    assert r.status_code==201,r.text
    assert not r.json()['duplicate']
    assert c.post(endpoint,headers=h,json=good).json()['duplicate']
    analyses=c.get('/api/meeting-review/transcripts/trans1/analyses').json()
    item=analyses[0]['items'][0]
    assert item['status']=='proposed' and item['evidence_quote'] in text
    approver=f"/api/meeting-review/items/{item['id']}/convert"
    assert c.post(approver,headers=h,json={'title':'Enviar a proposta comercial','project_id':'wrong'}).status_code==422
    ok=c.post(approver,headers=h,json={'title':'Enviar proposta comercial'})
    assert ok.status_code==200,ok.text
    task_id=ok.json()['id']
    assert c.post(approver,headers=h,json={'title':'Enviar proposta comercial'}).json()=={'id':task_id,'duplicate':True}
    assert c.get('/api/tasks').json()[0]['id']==task_id
    assert c.post(f"/api/meeting-review/items/{item['id']}/dismiss",headers=h,json={}).status_code==409
    assert len(c.get('/api/meeting-review/search?q=proposta').json()['results'])==1
    assert c.get('/api/meeting-review/search?q=orcamento').json()['results'][0]['offset'] == text.index('orçamento')
    deletion=c.delete('/api/meeting-review/transcripts/trans1',headers=h)
    assert deletion.status_code==200,deletion.text
    assert c.get('/api/meeting-review/transcripts/trans1/package').status_code==404
    assert c.get('/api/tasks').json()[0]['id']==task_id
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM meeting_suggestions').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM meeting_analyses').fetchone()[0]==0


def test_validation_dismiss_and_independent_questions(tmp_path):
    c,h,_,text=setup(tmp_path)
    d=analysis(text)
    d['items'][0]['kind']='question'
    d['items'][0]['suggested_due_at']='next week'
    r=c.post('/api/meeting-review/transcripts/trans1/analyses',headers=h,json=d)
    assert r.status_code==201,r.text
    item=c.get('/api/meeting-review/transcripts/trans1/analyses').json()[0]['items'][0]
    url=f"/api/meeting-review/items/{item['id']}"
    assert c.post(url+'/convert',headers=h,json={'title':'Wrong'}).status_code==422
    assert c.post(url+'/dismiss',headers=h,json={}).status_code==200
    assert c.post(url+'/convert',headers=h,json={'title':'Wrong'}).status_code==422
