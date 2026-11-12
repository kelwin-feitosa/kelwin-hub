"""HORIZONTE privacy and read-only upgrade checks (temporary databases only)."""
import os
import sqlite3
import stat

import pytest

from hub.storage import Store, LATEST_SCHEMA_VERSION
from scripts.preflight import inspect_installation


def private_config(path):
    path.write_text(
        'HUB_PASSWORD_HASH=test-hash-not-a-real-credential\n'
        'HUB_SESSION_SECRET=test-secret-not-a-real-credential\n',
        encoding='utf-8')
    path.chmod(0o600)
    return path


@pytest.mark.skipif(os.name != 'posix', reason='POSIX mode bits')
def test_new_db_is_private_before_sqlite_creates_sidecars(tmp_path):
    directory = tmp_path / 'private'
    path = directory / 'hub.db'
    store = Store(str(path))
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with store.connection() as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


@pytest.mark.skipif(os.name != 'posix', reason='POSIX mode bits')
def test_existing_db_permissions_are_hardened_without_losing_data(tmp_path):
    path = tmp_path / 'existing.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE preserved(id TEXT PRIMARY KEY)')
        db.execute("INSERT INTO preserved VALUES ('keep')")
    path.chmod(0o644)
    Store(str(path))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT id FROM preserved').fetchone()[0] == 'keep'


def test_preflight_read_only_and_matching_schema(tmp_path):
    db_path = tmp_path / 'hub.db'
    Store(str(db_path))
    env = private_config(tmp_path / '.env')
    before = db_path.stat()
    result = inspect_installation(env, db_path)
    after = db_path.stat()
    assert result['status'] == 'ok', result
    assert result['schema_version'] == LATEST_SCHEMA_VERSION
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)


def test_preflight_rejects_foreign_key_orphan_without_changes(tmp_path):
    db_path = tmp_path / 'hub.db'
    Store(str(db_path))
    with sqlite3.connect(db_path) as db:
        db.execute('PRAGMA foreign_keys=OFF')
        db.execute("INSERT INTO opportunities(id,contact_id,title,kind,status,value_cents,next_action,created_at,updated_at) VALUES ('orphan','no-contact','Test','job','new',0,'Follow up','2026-11-12','2026-11-12')")
    env = private_config(tmp_path / '.env')
    result = inspect_installation(env, db_path)
    assert result['status'] == 'error'
    assert any('foreign_key_check' in error for error in result['errors'])
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT id FROM opportunities WHERE id='orphan'").fetchone() is not None


def test_preflight_rejects_missing_database_and_never_creates_it(tmp_path):
    db_path = tmp_path / 'absent.db'
    result = inspect_installation(private_config(tmp_path / '.env'), db_path)
    assert result['status'] == 'error'
    assert not db_path.exists()


@pytest.mark.skipif(os.name != 'posix', reason='POSIX mode bits')
def test_preflight_warns_on_insecure_env_file(tmp_path):
    db_path = tmp_path / 'hub.db'
    Store(str(db_path))
    env = private_config(tmp_path / '.env')
    env.chmod(0o644)
    result = inspect_installation(env, db_path)
    assert result['status'] == 'warning'
    assert any('.env' in warning for warning in result['warnings'])
