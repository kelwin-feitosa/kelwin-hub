-- Optional personal duration estimate; NULL remains the default for existing tasks.
ALTER TABLE tasks ADD COLUMN estimated_minutes INTEGER
  CHECK(estimated_minutes IS NULL OR estimated_minutes BETWEEN 5 AND 480);
