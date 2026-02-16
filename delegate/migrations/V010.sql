-- V10: magic commands support
-- Add 'result' column to store command output as JSON
ALTER TABLE messages ADD COLUMN result TEXT;

-- Add 'command' to the allowed message types
-- SQLite doesn't support ALTER TABLE to modify CHECK constraints,
-- so we recreate the table with the updated constraint.
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
    result      TEXT
);

-- Copy all data from old table to new table
INSERT INTO messages_new (id, timestamp, sender, recipient, content, type, task_id, delivered_at, seen_at, processed_at, result)
SELECT id, timestamp, sender, recipient, content, type, task_id, delivered_at, seen_at, processed_at, result
FROM messages;

-- Drop old table
DROP TABLE messages;

-- Rename new table to original name
ALTER TABLE messages_new RENAME TO messages;

-- Recreate all indexes
CREATE INDEX IF NOT EXISTS idx_messages_type
    ON messages(type);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp
    ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_sender_recipient
    ON messages(sender, recipient);
CREATE INDEX IF NOT EXISTS idx_messages_task_id
    ON messages(task_id);
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
