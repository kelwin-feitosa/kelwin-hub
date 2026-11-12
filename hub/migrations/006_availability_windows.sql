-- Private availability windows only; no public booking surface.
CREATE TABLE IF NOT EXISTS availability_windows (
  id TEXT PRIMARY KEY,
  weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6),
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  created_at TEXT NOT NULL,
  CHECK(length(start_time) = 5 AND length(end_time) = 5 AND start_time < end_time)
);
CREATE INDEX IF NOT EXISTS availability_weekday_idx ON availability_windows(weekday,start_time);
