-- Additive indexes for project/opportunity context lookups; no table rewrite.
CREATE INDEX IF NOT EXISTS task_project_context_idx ON tasks(project_id,status,due_at,created_at);
CREATE INDEX IF NOT EXISTS task_opportunity_context_idx ON tasks(opportunity_id,status,due_at,created_at);
