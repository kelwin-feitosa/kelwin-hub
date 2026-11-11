"""SQLite with short, explicit transactions and FK enforcement."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid

MIGRATIONS = Path(__file__).resolve().parent / "migrations"
LATEST_SCHEMA_VERSION = 1


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def new_id() -> str:
    return str(uuid.uuid4())


SCHEMA = '''
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, area TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('active','paused','completed','archived')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contacts (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, company TEXT NOT NULL DEFAULT '',
  email TEXT UNIQUE, phone TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT 'business', source TEXT NOT NULL DEFAULT 'manual',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opportunities (
  id TEXT PRIMARY KEY, contact_id TEXT NOT NULL REFERENCES contacts(id),
  title TEXT NOT NULL, kind TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('new','active','waiting','won','lost','archived')),
  value_cents INTEGER CHECK(value_cents >= 0),
  next_action TEXT NOT NULL, followup_at TEXT,
  last_contact_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS opportunity_contact_idx ON opportunities(contact_id);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, project_id TEXT REFERENCES projects(id),
  opportunity_id TEXT REFERENCES opportunities(id),
  status TEXT NOT NULL CHECK(status IN ('open','blocked','done')),
  priority INTEGER NOT NULL DEFAULT 1 CHECK(priority BETWEEN 0 AND 3),
  due_at TEXT, next_action TEXT NOT NULL DEFAULT '',
  completed_at TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS task_due_idx ON tasks(status, due_at);
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, start_at TEXT NOT NULL,
  end_at TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('proposed','confirmed','cancelled')),
  source TEXT NOT NULL DEFAULT 'local', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS automation_configs (
  code TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
  threshold_days INTEGER NOT NULL CHECK(threshold_days BETWEEN 1 AND 365),
  last_run_at TEXT
);
CREATE TABLE IF NOT EXISTS automation_runs (
  id TEXT PRIMARY KEY, code TEXT NOT NULL, status TEXT NOT NULL,
  scanned INTEGER NOT NULL, created INTEGER NOT NULL,
  executed_at TEXT NOT NULL, error TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY, code TEXT NOT NULL, entity_id TEXT NOT NULL,
  title TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('open','resolved','dismissed')),
  created_at TEXT NOT NULL, closed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_open_alert ON alerts(code,entity_id) WHERE status='open';
CREATE TABLE IF NOT EXISTS audit (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, entity_id TEXT NOT NULL,
  action TEXT NOT NULL, at TEXT NOT NULL
);
INSERT OR IGNORE INTO automation_configs(code,enabled,threshold_days) VALUES ('stale_opportunities',1,5);
'''


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            current = db.execute('PRAGMA user_version').fetchone()[0]
            if current > LATEST_SCHEMA_VERSION:
                raise RuntimeError('Banco de versão superior ao aplicativo; atualização necessária')
            db.executescript(SCHEMA)
            for version in range(current + 1, LATEST_SCHEMA_VERSION + 1):
                sql = (MIGRATIONS / f'{version:03d}_sessions_scheduler_integrity.sql').read_text(encoding='utf-8')
                # The migration, data preservation and version bump are one transaction.
                # executescript() commits its prior transaction; BEGIN lives inside the script.
                db.executescript(f'BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version={version};\nCOMMIT;')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=10000')
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.execute('COMMIT')
            except Exception:
                db.execute('ROLLBACK')
                raise


def rows(result):
    return [dict(row) for row in result.fetchall()]


def record(db, kind, ident, action):
    db.execute('INSERT INTO audit VALUES (?,?,?,?,?)', (new_id(), kind, ident, action, now_utc()))