-- V16: UUID columns on all data tables
-- messages
ALTER TABLE messages ADD COLUMN team_uuid TEXT NOT NULL DEFAULT '';
ALTER TABLE messages ADD COLUMN sender_uuid TEXT NOT NULL DEFAULT '';
ALTER TABLE messages ADD COLUMN recipient_uuid TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_messages_team_uuid ON messages(team_uuid);
CREATE INDEX IF NOT EXISTS idx_messages_team_uuid_recipient_uuid ON messages(team_uuid, recipient_uuid);
CREATE INDEX IF NOT EXISTS idx_messages_recipient_uuid_unread ON messages(recipient_uuid, delivered_at) WHERE type='chat' AND processed_at IS NULL;

-- sessions
ALTER TABLE sessions ADD COLUMN team_uuid TEXT NOT NULL DEFAULT '';
ALTER TABLE sessions ADD COLUMN agent_uuid TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_sessions_team_uuid_agent_uuid ON sessions(team_uuid, agent_uuid);

-- tasks
ALTER TABLE tasks ADD COLUMN team_uuid TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN dri_uuid TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN assignee_uuid TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_tasks_team_uuid_status ON tasks(team_uuid, status);
CREATE INDEX IF NOT EXISTS idx_tasks_team_uuid_id ON tasks(team_uuid, id);

-- task_comments
ALTER TABLE task_comments ADD COLUMN team_uuid TEXT NOT NULL DEFAULT '';
ALTER TABLE task_comments ADD COLUMN author_uuid TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_task_comments_team_uuid_task_id ON task_comments(team_uuid, task_id);

-- reviews
ALTER TABLE reviews ADD COLUMN team_uuid TEXT NOT NULL DEFAULT '';
ALTER TABLE reviews ADD COLUMN reviewer_uuid TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_reviews_team_uuid_task_id ON reviews(team_uuid, task_id);

-- review_comments
ALTER TABLE review_comments ADD COLUMN team_uuid TEXT NOT NULL DEFAULT '';
ALTER TABLE review_comments ADD COLUMN author_uuid TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_review_comments_team_uuid ON review_comments(team_uuid, task_id, attempt);
