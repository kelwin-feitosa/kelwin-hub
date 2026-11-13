"""Dry-run old-schema -> current upgrade and encrypted restore on fictional data.

Never accepts a production database path. Uses a private temporary directory
and creates all records locally. Install the optional 'backup' extra first.
"""
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from hub.storage import Store, SCHEMA, MIGRATIONS, MIGRATION_NAMES, LATEST_SCHEMA_VERSION
from scripts.backup import backup_db, restore_db

TEST_PASSWORD='Synthetic-rehearsal-password-2026!'


def make_v7_database(path:Path):
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        for version in range(1,8):
            migration=(MIGRATIONS/MIGRATION_NAMES[version]).read_text(encoding='utf-8')
            db.executescript(f'BEGIN IMMEDIATE;\n{migration}\nPRAGMA user_version={version};\nCOMMIT;')
        db.execute("INSERT INTO projects VALUES ('project-test','Projeto fictício','estudos','active','2026-11-12')")
        db.execute("INSERT INTO tasks VALUES ('task-test','Tarefa fictícia','project-test',NULL,'open',2,NULL,'',NULL,'2026-11-12')")
        assert db.execute('PRAGMA user_version').fetchone()[0]==7


def validate(path:Path):
    with Store(str(path)).connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==LATEST_SCHEMA_VERSION
        assert db.execute("SELECT title,estimated_minutes FROM tasks WHERE id='task-test'").fetchone()==('Tarefa fictícia',None)
        assert db.execute("SELECT name FROM projects WHERE id='project-test'").fetchone()[0]=='Projeto fictício'
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def rehearse():
    with tempfile.TemporaryDirectory(prefix='kh16-rehearsal-') as directory:
        root=Path(directory)
        initial=root/'synthetic-v7.db'
        encrypted=root/'synthetic-only.khb'
        restored=root/'restored-v7.db'
        make_v7_database(initial)
        backup_db(initial,encrypted,TEST_PASSWORD)
        assert encrypted.exists() and encrypted.read_bytes().startswith(b'KHB1')
        validate(initial)  # applies the actual migration on the fictional source
        restore_db(encrypted,restored,TEST_PASSWORD)
        validate(restored)  # upgrade the separately restored historical backup
        return {'ok':True,'from_schema':7,'to_schema':LATEST_SCHEMA_VERSION,
                'preserved_tasks':1,'restored_tasks':1,'encrypted_backup':True}


def main():
    result=rehearse()
    print('Ensaio sintético de atualização e restauração:',result)


if __name__=='__main__':
    main()
