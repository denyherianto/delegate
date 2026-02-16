-- V13: Workflow columns on tasks
ALTER TABLE tasks ADD COLUMN workflow TEXT NOT NULL DEFAULT 'default';
ALTER TABLE tasks ADD COLUMN workflow_version INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_tasks_workflow ON tasks(workflow);
