-- Additive notes: ties to existing entities via real foreign keys; no legacy rewrite.
CREATE TABLE IF NOT EXISTS notes (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  project_id TEXT REFERENCES projects(id),
  contact_id TEXT REFERENCES contacts(id),
  opportunity_id TEXT REFERENCES opportunities(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK(length(trim(title)) > 0),
  CHECK(length(trim(body)) > 0)
);
CREATE INDEX IF NOT EXISTS notes_updated_idx ON notes(updated_at DESC);
CREATE INDEX IF NOT EXISTS notes_project_idx ON notes(project_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS notes_contact_idx ON notes(contact_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS notes_opportunity_idx ON notes(opportunity_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS audit_lookup_idx ON audit(kind, entity_id, at DESC);
