"""Missao 9: fixtures ficticios, regressions derived from Mission 8 evidence."""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest
from fastapi.testclient import TestClient

from hub.api import create_app
from hub.security import hash_password
from hub.storage import SCHEMA, Store


@pytest.mark.parametrize(('endpoint', 'payload'), [
    ('/api/projects', {'name': ' \t\n', 'area': 'pessoal'}),
    ('/api/projects', {'name': '\u2003\u2009'}),
    ('/api/contacts', {'name': '\t \n'}),
    ('/api/opportunities', {'title': '\u2003', 'next_action': 'Telefonar'}),
    ('/api/opportunities', {'title': 'Projeto ficticio', 'next_action': ' \t '}),
    ('/api/tasks', {'title': '  \u2003 '}),
    ('/api/events', {'title': ' \t ', 'start_at': '2026-11-15T10:00', 'end_at': '2026-11-15T11:00'}),
])
def test_required_text_rejects_whitespace(ctx, endpoint, payload):
    client, headers, _ = ctx
    if endpoint == '/api/opportunities':
        contact = client.post('/api/contacts', headers=headers, json={'name': 'Contato Ficticio'})
        payload = {'contact_id': contact.json()['id'], **payload}
    response = client.post(endpoint, headers=headers, json=payload)
    assert response.status_code == 422, response.text


def test_project_null_status_returns_validation_not_500(ctx):
    client, headers, _ = ctx
    project = client.post('/api/projects', headers=headers, json={'name': 'Projeto Ficticio'}).json()['id']
    response = client.patch(f'/api/projects/{project}', headers=headers, json={'status': None})
    assert response.status_code == 422
    assert client.get('/api/projects').json()[0]['status'] == 'active'


def test_existing_session_cookie_is_revoked_after_logout(tmp_path):
    app = create_app(str(tmp_path / 'sessions.db'), password_hash=hash_password('Senha-ficticia-2026!'), session_secret='S'*48, scheduler=False)
    with TestClient(app) as client:
        assert client.post('/api/login', json={'password': 'Senha-ficticia-2026!'}).status_code == 200
        captured = client.cookies.get('kh_session')
        csrf = client.get('/api/session').json()['csrf']
        assert client.post('/api/logout', headers={'X-CSRF-Token': csrf}).status_code == 200
        # Simulate copying an old cookie into a fresh browser after logout.
        with TestClient(app) as replay:
            replay.cookies.set('kh_session', captured)
            assert replay.get('/api/session').json()['authenticated'] is False
            assert replay.get('/api/projects').status_code == 401


def test_versioned_upgrade_preserves_existing_data(tmp_path):
    old_path = tmp_path / 'v7.db'
    with sqlite3.connect(old_path) as db:
        db.executescript(SCHEMA)
        db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',
                   ('old-project', 'Projeto Legado', 'pessoal', 'active', '2026-11-10T00:00:00+00:00'))
        assert db.execute('PRAGMA user_version').fetchone()[0] == 0
    store = Store(str(old_path))
    with store.connection() as db:
        assert db.execute('SELECT name FROM projects WHERE id=?', ('old-project',)).fetchone()[0] == 'Projeto Legado'
        assert db.execute('PRAGMA user_version').fetchone()[0] >= 1
        assert db.execute("SELECT name FROM sqlite_master WHERE name='sessions'").fetchone()
    # Upgrade can be run twice without changing existing data.
    Store(str(old_path))
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM projects').fetchone()[0] == 1


def test_scheduler_state_is_exposed_to_authenticated_owner(ctx):
    client, headers, _ = ctx
    assert client.get('/api/automation-health').status_code == 200
    assert client.get('/api/automation-health').json()['scheduler_enabled'] is False
    assert client.get('/api/automation-health').json()['last_failure_type'] is None
    assert client.get('/api/automation-health', headers={'Cookie': 'kh_session=invalid'}).status_code in (200, 401)


def test_invalid_next_action_update_is_rejected(ctx):
    client, headers, _ = ctx
    contact = client.post('/api/contacts', headers=headers, json={'name': 'Ficticio'}).json()['id']
    opportunity = client.post('/api/opportunities', headers=headers,
        json={'contact_id': contact, 'title': 'Teste', 'next_action': 'Ligar'}).json()['id']
    assert client.patch(f'/api/opportunities/{opportunity}', headers=headers,
        json={'next_action': '\u2009  '}).status_code == 422
    assert client.get('/api/opportunities').json()[0]['next_action'] == 'Ligar'


def test_sessions_survive_restart_and_logout_revokes_persistently(tmp_path):
    database = str(tmp_path / 'relogin.db')
    config = {'password_hash': hash_password('Senha-ficticia-2026!'),
              'session_secret': 'S'*48, 'scheduler': False}
    app = create_app(database, **config)
    with TestClient(app) as first:
        first.post('/api/login', json={'password':'Senha-ficticia-2026!'})
        cookie = first.cookies.get('kh_session')
        assert first.get('/api/session').json()['authenticated']
    with TestClient(create_app(database, **config)) as second:
        second.cookies.set('kh_session', cookie)
        assert second.get('/api/session').json()['authenticated']
        csrf = second.get('/api/session').json()['csrf']
        assert second.post('/api/logout', headers={'X-CSRF-Token': csrf}).status_code == 200
    with TestClient(create_app(database, **config)) as third:
        third.cookies.set('kh_session', cookie)
        assert not third.get('/api/session').json()['authenticated']


def test_migration_triggers_disallow_blank_new_write_but_preserve_legacy(tmp_path):
    path = tmp_path / 'legacy.db'
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',
                   ('old', ' ', 'personal', 'active', '2026-11-10T00:00:00+00:00'))
    store = Store(str(path))
    with store.connection() as db:
        assert db.execute('SELECT name FROM projects WHERE id=?', ('old',)).fetchone()[0] == ' '
    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction() as db:
            db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',
                       ('new', ' ', 'personal', 'active', '2026-11-10T00:00:00+00:00'))
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM projects').fetchone()[0] == 1


def test_scheduler_catches_up_after_restart(tmp_path):
    import time
    db = str(tmp_path / 'catchup.db')
    config = {'password_hash':hash_password('Senha-ficticia-2026!'),
              'session_secret':'S'*48, 'scheduler':False}
    app = create_app(db, **config)
    with TestClient(app) as client:
        client.post('/api/login', json={'password':'Senha-ficticia-2026!'})
        h = {'X-CSRF-Token':client.get('/api/session').json()['csrf']}
        cid = client.post('/api/contacts', headers=h, json={'name':'Cliente Ficticio'}).json()['id']
        opp = client.post('/api/opportunities', headers=h, json={
            'contact_id': cid, 'title':'Projeto ficticio', 'next_action':'Retomar contato'}).json()['id']
        with app.state.store.transaction() as conn:
            conn.execute('UPDATE opportunities SET created_at=? WHERE id=?',
                ((datetime.now(timezone.utc)-timedelta(days=10)).isoformat(timespec='seconds'), opp))
    config['scheduler'] = True
    with TestClient(create_app(db, **config)) as restarted:
        deadline = time.monotonic()+3
        while time.monotonic() < deadline:
            with restarted.app.state.store.connection() as conn:
                count = conn.execute('SELECT COUNT(*) FROM alerts WHERE status=?', ('open',)).fetchone()[0]
            if count: break
            time.sleep(.05)
        assert count == 1
        with restarted.app.state.store.connection() as conn:
            assert conn.execute('SELECT last_check_at FROM scheduler_health').fetchone()[0]


def test_scheduler_failure_is_recorded_without_sensitive_message(tmp_path, monkeypatch, caplog):
    import time
    import hub.api as api_module

    def broken(*args, **kwargs):
        raise RuntimeError('PRIVATE-MESSAGE-MUST-NOT-APPEAR')

    monkeypatch.setattr(api_module, 'safe_run_stale', broken)
    db = str(tmp_path / 'failure.db')
    app = create_app(db, password_hash=hash_password('Senha-ficticia-2026!'),
                     session_secret='S'*48, scheduler=True)
    with TestClient(app) as client:
        deadline = time.monotonic()+3
        while time.monotonic() < deadline:
            with app.state.store.connection() as conn:
                item = conn.execute('SELECT last_failure_type FROM scheduler_health WHERE id=1').fetchone()[0]
            if item: break
            time.sleep(.05)
        assert item == 'RuntimeError'
        assert 'PRIVATE-MESSAGE-MUST-NOT-APPEAR' not in caplog.text
        client.post('/api/login', json={'password':'Senha-ficticia-2026!'})
        assert client.get('/api/automation-health').json()['last_failure_type'] == 'RuntimeError'


def test_backup_restore_migrated_schema(tmp_path):
    from scripts.backup import backup_db, restore_db
    path = tmp_path / 'hub.db'
    store = Store(str(path))
    with store.transaction() as db:
        db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',
                   ('sample', 'Projeto Ficticio', 'pessoal', 'active', '2026-11-10T00:00:00+00:00'))
    backup = tmp_path / 'encrypted.khb'
    restored = tmp_path / 'restored.db'
    backup_db(path, backup, 'Senha-Ficticia-Backup-2026!')
    restore_db(backup, restored, 'Senha-Ficticia-Backup-2026!')
    with sqlite3.connect(restored) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1
        assert db.execute('SELECT name FROM projects WHERE id=?', ('sample',)).fetchone()[0] == 'Projeto Ficticio'
        assert db.execute('SELECT name FROM sqlite_master WHERE name="sessions"').fetchone()
    with pytest.raises(FileExistsError):
        restore_db(backup, restored, 'Senha-Ficticia-Backup-2026!')
