-- Additive local transcript imports; immutable content and preserved origin.
CREATE TABLE IF NOT EXISTS meeting_transcripts (
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES events(id),
  format TEXT NOT NULL CHECK(format IN ('txt','srt','vtt')),
  source_name TEXT NOT NULL DEFAULT '',
  content TEXT NOT NULL CHECK(length(trim(content)) > 0),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS transcripts_event_idx ON meeting_transcripts(event_id,created_at DESC);
