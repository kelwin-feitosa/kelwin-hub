-- Additive meeting context; no change to existing event time or status.
ALTER TABLE events ADD COLUMN project_id TEXT REFERENCES projects(id);
ALTER TABLE events ADD COLUMN contact_id TEXT REFERENCES contacts(id);
CREATE INDEX IF NOT EXISTS events_confirmed_range_idx ON events(status,start_at,end_at);
CREATE INDEX IF NOT EXISTS events_project_idx ON events(project_id,start_at);
CREATE INDEX IF NOT EXISTS events_contact_idx ON events(contact_id,start_at);
