"""Safe additive migration and indexing for NEXO contextual lookups."""
import sqlite3

from hub.storage import Store, SCHEMA, MIGRATIONS, MIGRATION_NAMES, LATEST_SCHEMA_VERSION


def test_upgrading_realistic_v6_database_preserves_records(tmp_path):
    path = str(tmp_path / 'previous-version.db')
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        # Genuine schema evolution to v6, not a current DB with a fake version.
        for version in range(1, 7):
            sql = (MIGRATIONS / MIGRATION_NAMES[version]).read_text(encoding='utf-8')
            db.executescript(f'BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version={version};\nCOMMIT;')
        db.execute("INSERT INTO projects VALUES ('project1','Preservado','pessoal','active','2026-11-11')")
        db.execute("INSERT INTO tasks VALUES ('task1','Tarefa mantida','project1',NULL,'open',1,NULL,'',NULL,'2026-11-11')")
        assert db.execute('PRAGMA user_version').fetchone()[0] == 6
    Store(path)
    # Reopening is idempotent and cannot destroy the old record.
    Store(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == LATEST_SCHEMA_VERSION == 8
        assert db.execute('SELECT title FROM tasks WHERE id=?',('task1',)).fetchone()[0] == 'Tarefa mantida'
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        names = {row[1] for row in db.execute("PRAGMA index_list('tasks')")}
        assert {'task_project_context_idx','task_opportunity_context_idx'} <= names
        for column in ('project_id','opportunity_id'):
            plan = ' '.join(row[3] for row in db.execute(
                f'EXPLAIN QUERY PLAN SELECT id FROM tasks WHERE {column}=?',('project1',)))
            assert 'USING INDEX' in plan or 'USING COVERING INDEX' in plan, plan


def test_new_install_also_has_context_indexes(tmp_path):
    store = Store(str(tmp_path/'fresh.db'))
    with store.connection() as db:
        names={r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert 'task_project_context_idx' in names
        assert 'task_opportunity_context_idx' in names