"""Local SQLite parent symlinks must match the read-only preflight policy."""
from pathlib import Path
import os

import pytest
from hub.storage import Store


@pytest.mark.skipif(os.name != 'posix', reason='POSIX symbolic links')
def test_store_rejects_symlinked_data_directory_without_creating_database(tmp_path):
    real=tmp_path/'private-data'
    real.mkdir(mode=0o700)
    link=tmp_path/'indirect-data'
    link.symlink_to(real,target_is_directory=True)

    with pytest.raises(RuntimeError,match='Diretório.*simbólico'):
        Store(str(link/'hub.db'))
    assert not (real/'hub.db').exists()
    assert not any(real.iterdir())


@pytest.mark.skipif(os.name != 'posix', reason='POSIX symbolic links')
def test_store_still_accepts_regular_private_directory(tmp_path):
    data=tmp_path/'real-data'
    db=data/'hub.db'
    store=Store(str(db))
    with store.connection() as connection:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert db.exists()
    assert not data.is_symlink()
