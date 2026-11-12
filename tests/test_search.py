"""Public HTTP security and user-visible data for local unified search."""
import re


def test_search_requires_login(tmp_path):
    from fastapi.testclient import TestClient
    from hub.api import create_app
    from hub.security import hash_password
    app = create_app(str(tmp_path / 'test.db'),password_hash=hash_password('fictitious-password-123'),
                     session_secret='testing-only-' * 5,scheduler=False)
    with TestClient(app) as c:
        assert c.get('/api/search', params={'q':'projeto'}).status_code == 401


def test_search_across_entities_with_relations_and_accents(ctx):
    client, csrf, _ = ctx
    pid = client.post('/api/projects',json={'name':'Música Computacional','area':'estudo'},headers=csrf).json()['id']
    cid = client.post('/api/contacts',json={'name':'Ana Júlia','company':'Fábrica Acústica','email':'ana@musica.example'},headers=csrf).json()['id']
    oid = client.post('/api/opportunities',json={'contact_id':cid,'title':'Revisão MusicXML',
            'next_action':'Enviar proposta técnica','kind':'music'},headers=csrf).json()['id']
    tid = client.post('/api/tasks',json={'title':'Revisar partituras','project_id':pid,'opportunity_id':oid},headers=csrf).json()['id']
    resp=client.get('/api/search',params={'q':'musica'})
    assert resp.status_code==200
    found=resp.json()['results']
    assert (pid,'projects') in {(x['id'],x['kind']) for x in found}
    assert (cid,'contacts') in {(x['id'],x['kind']) for x in found}
    assert (tid,'tasks') in {(x['id'],x['kind']) for x in found}
    assert (oid,'opportunities') in {(x['id'],x['kind']) for x in found}
    assert (cid,'contacts') in {(x['id'],x['kind']) for x in client.get('/api/search',params={'q':'Fabrica'}).json()['results']}
    assert any(x['id']==tid for x in client.get('/api/search',params={'q':'Computacional'}).json()['results'])
    assert any(x['id']==oid for x in client.get('/api/search',params={'q':'Ana Julia'}).json()['results'])


def test_search_validates_input_and_does_not_treat_wildcards_as_sql(ctx):
    client, csrf, _=ctx
    for q in ('', 'a', ' '*6, 'A'*101):
        assert client.get('/api/search',params={'q':q}).status_code==422
    client.post('/api/projects',json={'name':'100% Real','area':'trabalho'},headers=csrf)
    assert len(client.get('/api/search',params={'q':'100%'}).json()['results'])==1
    # Literal percent and underscore cannot dump the entire table (not LIKE wildcards).
    assert not client.get('/api/search',params={'q':'%_'}).json()['results']
    assert not client.get('/api/search',params={'q':"' OR 1=1 --"}).json()['results']


def test_search_rank_and_does_not_mutate_database(ctx):
    client, csrf, store=ctx
    for title in ('Projeto Exato','Outro Projeto Exato','Projeto Extra'):
        client.post('/api/projects',json={'name':title,'area':'pessoal'},headers=csrf)
    with store.connection() as db:
        before=db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
    results=client.get('/api/search',params={'q':'Projeto Exato'}).json()['results']
    assert results[0]['title']=='Projeto Exato'
    assert len(results)>=2
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]==before
    assert client.get('/api/search',params={'q':'inexistente'}).json()['results']==[]


def test_frontend_search_has_accessible_dialog_and_safe_escaping():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    html=(root/'hub/static/index.html').read_text()
    js=(root/'hub/static/app.js').read_text()
    assert 'id="search-dialog"' in html and 'id="search-query"' in html
    assert 'id="search-results"' in html and 'aria-live="polite"' in html
    assert 'Control+K Meta+K' in html
    assert 'encodeURIComponent(raw)' in js
    assert 'safe(item.title)' in js and 'safe(item.detail)' in js
    assert 'searchPreviousFocus?.focus?.()' in js
    assert re.search(r'const busy=.*search-dialog',js)
