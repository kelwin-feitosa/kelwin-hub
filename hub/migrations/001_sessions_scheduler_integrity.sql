-- 9.0 additive migration. Does not rewrite or delete legacy user rows.
CREATE TABLE IF NOT EXISTS sessions (
  nonce TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
CREATE TABLE IF NOT EXISTS scheduler_health (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  last_check_at TEXT,
  last_success_at TEXT,
  last_failure_at TEXT,
  last_failure_type TEXT
);
INSERT OR IGNORE INTO scheduler_health(id) VALUES (1);
-- Compatibility: historical whitespace-only rows are NOT silently altered.
-- Triggers ensure new writes do not introduce these invalid values.
CREATE TRIGGER IF NOT EXISTS projects_required_insert BEFORE INSERT ON projects
WHEN length(trim(NEW.name))=0 OR length(trim(NEW.area))=0
BEGIN SELECT RAISE(ABORT,'project required field blank'); END;
CREATE TRIGGER IF NOT EXISTS projects_required_update BEFORE UPDATE OF name,area ON projects
WHEN length(trim(NEW.name))=0 OR length(trim(NEW.area))=0
BEGIN SELECT RAISE(ABORT,'project required field blank'); END;
CREATE TRIGGER IF NOT EXISTS contacts_required_insert BEFORE INSERT ON contacts
WHEN length(trim(NEW.name))=0
BEGIN SELECT RAISE(ABORT,'contact name blank'); END;
CREATE TRIGGER IF NOT EXISTS contacts_required_update BEFORE UPDATE OF name ON contacts
WHEN length(trim(NEW.name))=0
BEGIN SELECT RAISE(ABORT,'contact name blank'); END;
CREATE TRIGGER IF NOT EXISTS opportunities_required_insert BEFORE INSERT ON opportunities
WHEN length(trim(NEW.title))=0 OR length(trim(NEW.next_action))=0
BEGIN SELECT RAISE(ABORT,'opportunity required field blank'); END;
CREATE TRIGGER IF NOT EXISTS opportunities_required_update BEFORE UPDATE OF title,next_action ON opportunities
WHEN length(trim(NEW.title))=0 OR length(trim(NEW.next_action))=0
BEGIN SELECT RAISE(ABORT,'opportunity required field blank'); END;
CREATE TRIGGER IF NOT EXISTS tasks_required_insert BEFORE INSERT ON tasks
WHEN length(trim(NEW.title))=0
BEGIN SELECT RAISE(ABORT,'task title blank'); END;
CREATE TRIGGER IF NOT EXISTS tasks_required_update BEFORE UPDATE OF title ON tasks
WHEN length(trim(NEW.title))=0
BEGIN SELECT RAISE(ABORT,'task title blank'); END;
CREATE TRIGGER IF NOT EXISTS events_required_insert BEFORE INSERT ON events
WHEN length(trim(NEW.title))=0
BEGIN SELECT RAISE(ABORT,'event title blank'); END;
