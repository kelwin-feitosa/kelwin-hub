"""Follow-up groups are facts based on dates/status, not invented AI decisions."""
from datetime import datetime, timedelta, timezone

from hub.opportunity_board import load_board


def test_board_requires_login(tmp_path):
    from fastapi.testclient import TestClient
    from hub.api import create_app
    from hub.security import hash_password
    app=create_app(str(tmp_path/'db.sqlite'),password_hash=hash_password('fictitious-password-123'),
                   session_secret='secret-tests-'*5,scheduler=False)
    with TestClient(app) as client:
        assert client.get('/api/opportunities/board').status_code==401


def test_board_explainable_followups_without_data_duplication(ctx):
    c,csrf,store=ctx
    cid=c.post('/api/contacts',json={'name':'Contato Fictício'},headers=csrf).json()['id']
    start=datetime.now(timezone.utc)
    def add(name,when=None):
        payload={'contact_id':cid,'title':name,'next_action':'Verificar resposta'}
        if when is not None:payload['followup_at']=when.isoformat()
        return c.post('/api/opportunities',json=payload,headers=csrf).json()['id']
    past=add('Passou do prazo',start-timedelta(days=3))
    soon=add('Retorno próximo',start+timedelta(days=2))
    future=add('Retorno distante',start+timedelta(days=18))
    waiting=add('Aguardando sem data')
    undated=add('Ativa sem data')
    closed=add('Já encerrada',start-timedelta(days=4))
    c.patch('/api/opportunities/'+waiting,headers=csrf,json={'status':'waiting'})
    c.patch('/api/opportunities/'+closed,headers=csrf,json={'status':'won'})
    fixed=load_board(store,now=start)
    assert fixed['counts']=={'overdue':1,'upcoming':1,'later':1,'awaiting':1,'undated':1,'closed':1}
    assert fixed['groups']['overdue'][0]['id']==past
    assert fixed['groups']['upcoming'][0]['id']==soon
    assert fixed['groups']['later'][0]['id']==future
    assert fixed['groups']['awaiting'][0]['id']==waiting
    assert fixed['groups']['undated'][0]['id']==undated
    assert fixed['groups']['closed'][0]['id']==closed
    # A read-only board does not mark a follow-up as contacted or completed.
    response=c.get('/api/opportunities/board')
    assert response.status_code==200
    assert sum(response.json()['counts'].values())==6
    with store.connection() as db:
        audit=db.execute("SELECT COUNT(*) FROM audit WHERE action='contact'").fetchone()[0]
        assert audit==0


def test_board_is_authoritative_and_updates_after_contact_edit(ctx):
    c,csrf,_=ctx
    cid=c.post('/api/contacts',json={'name':'Outro contato'},headers=csrf).json()['id']
    oid=c.post('/api/opportunities',json={'contact_id':cid,'title':'Proposta técnica','next_action':'Responder'},headers=csrf).json()['id']
    before=c.get('/api/opportunities/board').json()['counts']
    assert before['undated']==1
    c.patch('/api/opportunities/'+oid,json={'status':'archived'},headers=csrf)
    after=c.get('/api/opportunities/board').json()['counts']
    assert after['closed']==1 and after['undated']==0


def test_board_interface_filters_and_safe_rendering():
    from pathlib import Path
    js=(Path(__file__).resolve().parents[1]/'hub/static/app.js').read_text()
    assert "async function opportunitiesView()" in js
    assert "function renderOpportunityBoard(board)" in js
    assert "function opportunityRow(x)" in js
    assert "safe(x.next_action)" in js and "safe(x.contact_name)" in js
    assert 'id="opp-filter-status"' in js
    assert 'id="opp-filter-kind"' in js
    assert 'aria-live="polite"' in js
