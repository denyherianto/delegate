-- V12: Multi-team support
-- Create teams metadata table
CREATE TABLE IF NOT EXISTS teams (
    name        TEXT PRIMARY KEY,
    team_id     TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Add team column to messages (requires table recreation since V10 just recreated it)
CREATE TABLE messages_new (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    sender      TEXT    NOT NULL,
    recipient   TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    type        TEXT    NOT NULL CHECK(type IN ('chat', 'event', 'command')),
    task_id     INTEGER,
    delivered_at TEXT,
    seen_at     TEXT,
    processed_at TEXT,
    result      TEXT,
    team        TEXT    NOT NULL DEFAULT ''
);

INSERT INTO messages_new (id, timestamp, sender, recipient, content, type, task_id, delivered_at, seen_at, processed_at, result, team)
SELECT id, timestamp, sender, recipient, content, type, task_id, delivered_at, seen_at, processed_at, result, ''
FROM messages;

DROP TABLE messages;
ALTER TABLE messages_new RENAME TO messages;

-- Recreate all messages indexes with team
CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_sender_recipient ON messages(sender, recipient);
CREATE INDEX IF NOT EXISTS idx_messages_task_id ON messages(task_id);
CREATE INDEX IF NOT EXISTS idx_messages_recipient_unread
    ON messages(recipient, delivered_at)
    WHERE type = 'chat' AND processed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_messages_sender
    ON messages(sender)
    WHERE type = 'chat';
CREATE INDEX IF NOT EXISTS idx_messages_undelivered
    ON messages(id)
    WHERE type = 'chat' AND delivered_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_messages_recipient_processed
    ON messages(recipient, processed_at)
    WHERE type = 'chat' AND processed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_recipient_sender_processed
    ON messages(recipient, sender, processed_at)
    WHERE type = 'chat' AND processed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_task_type
    ON messages(task_id, type);
CREATE INDEX IF NOT EXISTS idx_messages_task_ts
    ON messages(task_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_team_recipient ON messages(team, recipient);

-- Add team column to sessions
ALTER TABLE sessions ADD COLUMN team TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_sessions_team_agent ON sessions(team, agent);
CREATE INDEX IF NOT EXISTS idx_sessions_team_task_id ON sessions(team, task_id);

-- Add team column to tasks
ALTER TABLE tasks ADD COLUMN team TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_tasks_team_status ON tasks(team, status);
CREATE INDEX IF NOT EXISTS idx_tasks_team_id ON tasks(team, id);

-- Add team column to reviews
ALTER TABLE reviews ADD COLUMN team TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_reviews_team_task_id ON reviews(team, task_id);

-- Add team column to review_comments
ALTER TABLE review_comments ADD COLUMN team TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_review_comments_team_task_attempt ON review_comments(team, task_id, attempt);

-- Add team column to task_comments
ALTER TABLE task_comments ADD COLUMN team TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_task_comments_team_task_id ON task_comments(team, task_id);
