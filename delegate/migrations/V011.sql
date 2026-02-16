-- V11: composite indexes for activity queries
CREATE INDEX IF NOT EXISTS idx_messages_task_type
    ON messages(task_id, type);
CREATE INDEX IF NOT EXISTS idx_messages_task_ts
    ON messages(task_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_task_comments_task_ts
    ON task_comments(task_id, created_at);
