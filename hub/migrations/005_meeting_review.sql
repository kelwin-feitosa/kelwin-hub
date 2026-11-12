-- Meeting review 13.0: additive, consent-driven import and human-approved tasks.
CREATE TABLE IF NOT EXISTS meeting_analyses (
  id TEXT PRIMARY KEY,
  transcript_id TEXT NOT NULL REFERENCES meeting_transcripts(id) ON DELETE CASCADE,
  transcript_hash TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE (transcript_id,payload_hash)
);
CREATE INDEX IF NOT EXISTS meeting_analyses_transcript_idx ON meeting_analyses(transcript_id,created_at DESC);
CREATE TABLE IF NOT EXISTS meeting_suggestions (
  id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL REFERENCES meeting_analyses(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('action','decision','question')),
  title TEXT NOT NULL CHECK(length(trim(title))>0),
  detail TEXT NOT NULL DEFAULT '',
  evidence_start INTEGER NOT NULL CHECK(evidence_start >= 0),
  evidence_end INTEGER NOT NULL CHECK(evidence_end > evidence_start),
  evidence_quote TEXT NOT NULL,
  suggested_due_at TEXT,
  status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','dismissed','converted')),
  task_id TEXT UNIQUE REFERENCES tasks(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS meeting_suggestions_analysis_idx ON meeting_suggestions(analysis_id,status);
