"""M16 personal capacity: only user-declared estimates, no corporate data."""
from datetime import datetime
import sqlite3

import pytest
from hub.storage import Store, SCHEMA, MIGRATIONS, MIGRATION_NAMES, LATEST_SCHEMA_VERSION


def add(client, headers, title, **extra):
    result = client.post('/api/tasks', headers=headers, json={'title': title, **extra})
    assert result.status_code == 201, result.text
    return result.json()['id']


def test_focus_matches_only_open_tasks_with_known_estimates(ctx):
    client, heads, store = ctx
    short = add(client, heads, 'Revisar Python', estimated_minutes=15)
    exact = add(client, heads, 'Praticar flauta', estimated_minutes=30)
    long = add(client, heads, 'Estudo mais longo', estimated_minutes=90)
    unknown = add(client, heads, 'Curso ainda não estimado')
    blocked = add(client, heads, 'Dependendo de alguém', estimated_minutes=10)
    completed = add(client, heads, 'Finalizado', estimated_minutes=5)
    client.patch(f'/api/tasks/{blocked}', headers=heads, json={'status':'blocked'})
    client.patch(f'/api/tasks/{completed}', headers=heads, json={'status':'done'})
    response = client.get('/api/focus?minutes=30')
    assert response.status_code == 200
    data = response.json()
    assert {item['id'] for item in data['items']} == {short, exact}
    assert data['unestimated_open_tasks'] == 1
    assert data['minutes'] == 30
    assert 'não verifica sua agenda' in data['notice']
    with store.connection() as db:
        assert db.execute('SELECT estimated_minutes FROM tasks WHERE id=?',(long,)).fetchone()[0] == 90
        assert db.execute('SELECT estimated_minutes FROM tasks WHERE id=?',(unknown,)).fetchone()[0] is None


def test_estimate_can_be_added_changed_and_cleared(ctx):
    client, heads, _ = ctx
    ident = add(client, heads, 'Aprender uma técnica')
    for payload, expected in [({'estimated_minutes':25}, 25), ({'estimated_minutes':60},60),
                              ({'estimated_minutes':None},None)]:
        result = client.patch('/api/tasks/'+ident,headers=heads,json=payload)
        assert result.status_code == 200, result.text
        record = next(t for t in client.get('/api/tasks').json() if t['id']==ident)
        assert record['estimated_minutes'] == expected


@pytest.mark.parametrize('invalid', [0,1,4,481,9999,-20,30.5,'unknown'])
def test_task_estimate_rejects_invalid_values(ctx,invalid):
    client, heads, _ = ctx
    r=client.post('/api/tasks',headers=heads,json={'title':'Tarefa fictícia','estimated_minutes':invalid})
    assert r.status_code==422,r.text


@pytest.mark.parametrize('minutes', [0,4,241,999,-1])
def test_focus_rejects_out_of_range_windows(ctx,minutes):
    client, _, _ = ctx
    assert client.get('/api/focus',params={'minutes':minutes}).status_code==422


def test_focus_requires_login(tmp_path):
    from fastapi.testclient import TestClient
    from hub.api import create_app
    from hub.security import hash_password
    app=create_app(str(tmp_path/'clean.db'),password_hash=hash_password('Senha-ficticia-2026'),
                   session_secret='S'*48,scheduler=False)
    with TestClient(app) as client:
        assert client.get('/api/focus?minutes=30').status_code==401


def test_upgrade_from_v7_retains_old_tasks_and_defaults_to_null(tmp_path):
    path=tmp_path/'legacy.db'
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        for ver in range(1,8):
            script=(MIGRATIONS / MIGRATION_NAMES[ver]).read_text(encoding='utf-8')
            db.executescript(f'BEGIN IMMEDIATE;\n{script}\nPRAGMA user_version={ver};\nCOMMIT;')
        db.execute("INSERT INTO tasks VALUES ('before','Preservada',NULL,NULL,'open',2,NULL,'',NULL,'2026-11-12')")
        assert db.execute('PRAGMA user_version').fetchone()[0]==7
    Store(str(path));Store(str(path))
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==LATEST_SCHEMA_VERSION==8
        assert db.execute('SELECT title,estimated_minutes FROM tasks WHERE id=?',('before',)).fetchone()==('Preservada',None)
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
