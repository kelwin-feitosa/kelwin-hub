from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from hub.security import hash_password, verify_password, sign_session, validate_session
from hub.storage import Store
from scripts.backup import backup_db,restore_db


def test_password_verify():
    encoded=hash_password('long-password-123')
    assert verify_password('long-password-123',encoded)
    assert not verify_password('wrong',encoded)
    assert not verify_password('hello','invalid')
    with pytest.raises(ValueError):hash_password('short')


def test_session_signature():
    secret='s'*48
    value=sign_session(secret)
    assert validate_session(secret,value)
    assert validate_session(secret+'x',value) is None
    assert validate_session(secret,value+'z') is None


def test_encrypted_backup_restore(tmp_path):
    store=Store(str(tmp_path/'source.db'))
    with store.transaction() as db:
        db.execute("INSERT INTO projects VALUES ('p1','Piloto','pessoal','active','2026-11-11T12:00:00+00:00')")
    encrypted=tmp_path/'backups'/'sample.khb'
    backup_db(Path(store.path),encrypted,'senha-de-backup-2026')
    assert encrypted.read_bytes().startswith(b'KHB1')
    assert b'Piloto' not in encrypted.read_bytes()
    with pytest.raises(ValueError):restore_db(encrypted,tmp_path/'bad.db','senha-errada-2026')
    target=tmp_path/'restored.db'
    restore_db(encrypted,target,'senha-de-backup-2026')
    with Store(str(target)).connection() as db:
        assert db.execute('SELECT name FROM projects').fetchone()[0]=='Piloto'
    with pytest.raises(FileExistsError):restore_db(encrypted,target,'senha-de-backup-2026')
    with pytest.raises(FileExistsError):backup_db(Path(store.path),encrypted,'senha-de-backup-2026')
