"""The documented fictional demo must keep working after schema additions."""
import sqlite3
import pytest

from scripts.demo_scenario import demo
from hub.storage import LATEST_SCHEMA_VERSION


def test_documented_demo_builds_latest_schema_with_fictional_data(tmp_path):
    path=tmp_path/'isolated-demo.db'
    demo(path)
    assert path.exists()
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==LATEST_SCHEMA_VERSION
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        row=db.execute('SELECT title, estimated_minutes FROM tasks').fetchone()
        assert row==('Preparar orçamento fictício',None)
        assert db.execute('SELECT COUNT(*) FROM projects').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM contacts').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0]==1


def test_demo_refuses_to_overwrite_existing_test_database(tmp_path):
    path=tmp_path/'already-created.db'
    demo(path)
    with pytest.raises(FileExistsError):
        demo(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
