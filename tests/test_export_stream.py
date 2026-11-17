"""H17-10: private export streaming retains JSON compatibility without bulk SQL rows."""
import pytest
from fastapi.testclient import TestClient

from hub.api import create_app
from hub.security import hash_password


def test_export_stream_preserves_all_tables_and_private_headers(ctx):
    client, headers, store = ctx
    with store.transaction() as db:
        db.executemany(
            """INSERT INTO notes(id,title,body,created_at,updated_at)
               VALUES(?,?,?,'2026-11-17','2026-11-17')""",
            [(f'n-{i:04d}',f'Nota fictícia {i}','Informação privada sintética')
             for i in range(180)])
    response=client.get('/api/export')
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='no-store'
    assert 'attachment' in response.headers['content-disposition']
    assert response.headers['content-type'].startswith('application/json')
    payload=response.json()
    assert payload['version']==1
    assert len(payload['notes'])==180
    assert 'privadas' in payload['warning']
    assert all(k in payload for k in
               ('projects','contacts','opportunities','tasks','events',
                'meeting_transcripts','meeting_analyses','meeting_suggestions',
                'automation_configs','automation_runs','alerts','audit'))


def test_export_does_not_materialize_bulk_rows_helper(ctx,monkeypatch):
    import hub.api as api_module
    client, _, store = ctx
    with store.transaction() as db:
        db.execute("""INSERT INTO notes(id,title,body,created_at,updated_at)
                      VALUES('private','Fictícia','Texto confidencial de teste',
                             '2026-11-17','2026-11-17')""")
    def forbidden(*args,**kwargs):
        raise AssertionError('Export must not use rows().fetchall()')
    monkeypatch.setattr(api_module,'rows',forbidden)
    response=client.get('/api/export')
    assert response.status_code==200,response.text
    assert response.json()['notes'][0]['body']=='Texto confidencial de teste'


def test_private_export_requires_login(tmp_path):
    app=create_app(str(tmp_path/'clean.db'),
                   password_hash=hash_password('Synthetic-test-password'),
                   session_secret='S'*48,scheduler=False)
    with TestClient(app) as client:
        assert client.get('/api/export').status_code==401
