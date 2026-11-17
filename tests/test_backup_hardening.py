"""Regression tests for backup/restore, without accessing the user's data."""
import io
import os
import sqlite3
import zipfile
from pathlib import Path

import pytest
from scripts import backup as module

PASSWORD = 'Somente-testes-2026!'


def source_db(path):
    with sqlite3.connect(path) as db:
        for table in ('projects', 'contacts', 'opportunities', 'tasks', 'automation_configs'):
            db.execute(f'CREATE TABLE {table} (id TEXT PRIMARY KEY)')
        db.execute("INSERT INTO projects VALUES ('item-preservado')")


def test_restore_preserves_existing_backup_format_and_private_permissions(tmp_path):
    source = tmp_path / 'source.db'
    source_db(source)
    backup = tmp_path / 'encrypted.khb'
    module.backup_db(source, backup, PASSWORD)
    assert backup.read_bytes().startswith(module.MAGIC)
    assert os.stat(backup).st_mode & 0o077 == 0
    restored = tmp_path / 'restored.db'
    module.restore_db(backup, restored, PASSWORD)
    assert os.stat(restored).st_mode & 0o077 == 0
    with sqlite3.connect(restored) as db:
        assert db.execute('SELECT id FROM projects').fetchone()[0] == 'item-preservado'


def test_restore_rejects_target_created_after_initial_check(tmp_path, monkeypatch):
    source = tmp_path / 'source.db'
    source_db(source)
    backup = tmp_path / 'encrypted.khb'
    module.backup_db(source, backup, PASSWORD)
    target = tmp_path / 'target.db'
    validate = module._valid
    def race(path):
        validate(path)
        target.write_bytes(b'precious file created concurrently')
    monkeypatch.setattr(module, '_valid', race)
    with pytest.raises(FileExistsError):
        module.restore_db(backup, target, PASSWORD)
    assert target.read_bytes() == b'precious file created concurrently'


def test_restore_rejects_oversized_or_extra_members(tmp_path, monkeypatch):
    source = tmp_path / 'source.db'
    source_db(source)
    backup = tmp_path / 'encrypted.khb'
    module.backup_db(source, backup, PASSWORD)
    target = tmp_path / 'restored.db'
    monkeypatch.setattr(module, 'MAX_RESTORE_DB_BYTES', 1024)
    with pytest.raises(ValueError, match='limite'):
        module.restore_db(backup, target, PASSWORD)
    assert not target.exists()
    monkeypatch.setattr(module, 'MAX_RESTORE_DB_BYTES', 512 * 1024 * 1024)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        z.writestr('hub.db', source.read_bytes())
        z.writestr('extras.txt', 'unexpected')
    salt = b'1' * 16
    backup.write_bytes(module.MAGIC + salt + module._fernet(PASSWORD, salt).encrypt(stream.getvalue()))
    with pytest.raises(ValueError, match='único'):
        module.restore_db(backup, target, PASSWORD)
    assert not target.exists()


def test_backup_exclusive_create_never_replaces_existing(tmp_path):
    source = tmp_path / 'source.db'
    source_db(source)
    backup = tmp_path / 'encrypted.khb'
    backup.write_bytes(b'unchanged')
    with pytest.raises(FileExistsError):
        module.backup_db(source, backup, PASSWORD)
    assert backup.read_bytes() == b'unchanged'

def test_backup_and_restore_reject_broken_foreign_keys(tmp_path):
    source = tmp_path / 'orphaned.db'
    source_db(source)
    # Simulate corruption introduced while SQLite foreign_keys was disabled.
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE dependents (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id))')
        db.execute("INSERT INTO dependents VALUES ('orphan', 'missing-parent')")
    backup = tmp_path / 'not-created.khb'
    with pytest.raises(ValueError, match='chave estrangeira'):
        module.backup_db(source, backup, PASSWORD)
    assert not backup.exists()

    # Independently exercise the restore path on an authenticated archive of
    # a corrupt database. It must never publish even a partially valid target.
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(source, arcname='hub.db')
    salt = b'2' * 16
    backup.write_bytes(module.MAGIC + salt + module._fernet(PASSWORD, salt).encrypt(stream.getvalue()))
    destination = tmp_path / 'must-not-appear.db'
    with pytest.raises(ValueError, match='chave estrangeira'):
        module.restore_db(backup, destination, PASSWORD)
    assert not destination.exists()


def test_backup_rejects_snapshot_that_cannot_be_restored(tmp_path, monkeypatch):
    source = tmp_path / 'oversized-synthetic.db'
    source_db(source)
    output = tmp_path / 'must-not-create.khb'
    assert source.stat().st_size > 2048
    # Simulate a smaller restore limit without allocating a huge SQLite file.
    monkeypatch.setattr(module, 'MAX_RESTORE_DB_BYTES', 2048)
    with pytest.raises(ValueError, match='limite de restauração'):
        module.backup_db(source, output, PASSWORD)
    assert not output.exists()


def test_backup_at_restore_size_limit_keeps_khb1_compatibility(tmp_path, monkeypatch):
    source = tmp_path / 'fits.db'
    source_db(source)
    monkeypatch.setattr(module, 'MAX_RESTORE_DB_BYTES', source.stat().st_size)
    encrypted = tmp_path / 'fits.khb'
    module.backup_db(source, encrypted, PASSWORD)
    restored = tmp_path / 'fits-restored.db'
    module.restore_db(encrypted, restored, PASSWORD)
    assert restored.stat().st_size == source.stat().st_size
    with sqlite3.connect(restored) as db:
        assert db.execute('SELECT id FROM projects').fetchone()[0] == 'item-preservado'
