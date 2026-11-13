"""Security gates and recoverability on synthetic temporary databases only."""
import os
from pathlib import Path
import sqlite3
import stat

import pytest

from hub.storage import Store, MIGRATION_NAMES, LATEST_SCHEMA_VERSION
from scripts.preflight import inspect_installation
from scripts.rehearse_upgrade import make_v7_database, rehearse


def env_config(path):
    path.write_text('HUB_PASSWORD_HASH=fake-hash-test-only\nHUB_SESSION_SECRET=fake-secret-test-only\n',
                    encoding='utf-8')
    path.chmod(0o600)
    return path


def test_login_rejects_unbounded_password_before_password_hash_work(ctx,monkeypatch):
    import hub.api as api
    client, _, _ = ctx
    def forbid(*args,**kwargs):
        raise AssertionError('password hash verification should not run')
    monkeypatch.setattr(api,'verify_password',forbid)
    assert client.post('/api/login',json={'password':'x'*257}).status_code==422
    assert client.post('/api/login',json={'password':''}).status_code==422


@pytest.mark.skipif(os.name != 'posix',reason='POSIX directory modes')
def test_store_rejects_group_world_writable_private_db_directory(tmp_path):
    directory=tmp_path/'untrusted'
    directory.mkdir()
    directory.chmod(0o777)
    try:
        with pytest.raises(RuntimeError,match='diretório|Diretório'):
            Store(str(directory/'hub.db'))
        assert not (directory/'hub.db').exists()
    finally:
        directory.chmod(0o700)


@pytest.mark.skipif(os.name != 'posix',reason='POSIX directory modes')
def test_preflight_flags_unsafe_directory_without_mutating_it(tmp_path):
    directory=tmp_path/'data';database=directory/'hub.db'
    Store(str(database))
    config=env_config(tmp_path/'.env')
    directory.chmod(0o777)
    before=database.stat().st_mtime_ns
    try:
        result=inspect_installation(config,database)
        assert result['status']=='error'
        assert any('escrita por outros usuários' in msg for msg in result['errors'])
        assert database.stat().st_mtime_ns==before
    finally:
        directory.chmod(0o700)


def test_preflight_rejects_env_symlink_without_reading_contents(tmp_path,monkeypatch):
    from scripts import preflight
    db=tmp_path/'hub.db';Store(str(db))
    real=env_config(tmp_path/'real-env')
    linked=tmp_path/'.env';linked.symlink_to(real)
    monkeypatch.setattr(preflight,'read_env',lambda _: (_ for _ in ()).throw(AssertionError('read followed symlink')))
    result=preflight.inspect_installation(linked,db)
    assert result['status']=='error'
    assert any('simbólico' in x for x in result['errors'])


@pytest.mark.skipif(os.name != 'posix',reason='POSIX sidecar permissions')
def test_preflight_warns_if_live_sqlite_wal_is_exposed(tmp_path):
    db=tmp_path/'hub.db';Store(str(db))
    config=env_config(tmp_path/'.env')
    connection=sqlite3.connect(db)
    try:
        connection.execute("INSERT INTO projects VALUES ('p1','Privado','pessoal','active','2026-11-13')")
        connection.commit()
        wal=Path(str(db)+'-wal')
        assert wal.exists()
        wal.chmod(0o644)
        result=inspect_installation(config,db)
        assert any('-wal' in msg for msg in result['warnings'])
        assert result['status']=='warning',result
    finally:
        connection.close()


def test_fictional_rehearsal_backups_before_upgrade_and_restores():
    result=rehearse()
    assert result['ok'] is True
    assert result['from_schema']==7 and result['to_schema']==LATEST_SCHEMA_VERSION
    assert result['preserved_tasks']==result['restored_tasks']==1


def test_interrupted_migration_rolls_back_transaction_and_can_retry(tmp_path,monkeypatch):
    db_file=tmp_path/'synthetic-v7.db'
    make_v7_database(db_file)
    bad=tmp_path/'bad-sql.sql'
    bad.write_text('ALTER TABLE tasks ADD COLUMN transient_field TEXT;\nTHIS WILL FAIL;',encoding='utf-8')
    monkeypatch.setitem(MIGRATION_NAMES,8,str(bad))
    with pytest.raises(sqlite3.OperationalError):
        Store(str(db_file))
    with sqlite3.connect(db_file) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==7
        assert 'transient_field' not in {row[1] for row in db.execute('PRAGMA table_info(tasks)')}
        assert db.execute("SELECT count(*) FROM tasks WHERE id='task-test'").fetchone()[0]==1
    monkeypatch.setitem(MIGRATION_NAMES,8,'008_task_estimate.sql')
    store=Store(str(db_file))
    with store.connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==8
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
