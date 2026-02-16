-- V1: messages + sessions
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    sender      TEXT    NOT NULL,
    recipient   TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    type        TEXT    NOT NULL CHECK(type IN ('chat', 'event'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    agent            TEXT    NOT NULL,
    task_id          INTEGER,
    started_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ended_at         TEXT,
    duration_seconds REAL    DEFAULT 0.0,
    tokens_in        INTEGER DEFAULT 0,
    tokens_out       INTEGER DEFAULT 0,
    cost_usd         REAL    DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_messages_type
    ON messages(type);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp
    ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_sender_recipient
    ON messages(sender, recipient);
CREATE INDEX IF NOT EXISTS idx_sessions_agent
    ON sessions(agent);
CREATE INDEX IF NOT EXISTS idx_sessions_task_id
    ON sessions(task_id);
