-- V9: merge mailbox into messages
-- Add lifecycle columns to messages table
ALTER TABLE messages ADD COLUMN delivered_at TEXT;
ALTER TABLE messages ADD COLUMN seen_at TEXT;
ALTER TABLE messages ADD COLUMN processed_at TEXT;

-- Copy lifecycle data from mailbox to messages for existing chat messages
-- Match on sender, recipient, content (body in mailbox, content in messages)
UPDATE messages
SET delivered_at = (
    SELECT mb.delivered_at FROM mailbox mb
    WHERE mb.sender = messages.sender
      AND mb.recipient = messages.recipient
      AND mb.body = messages.content
      AND mb.task_id IS messages.task_id
    LIMIT 1
),
seen_at = (
    SELECT mb.seen_at FROM mailbox mb
    WHERE mb.sender = messages.sender
      AND mb.recipient = messages.recipient
      AND mb.body = messages.content
      AND mb.task_id IS messages.task_id
    LIMIT 1
),
processed_at = (
    SELECT mb.processed_at FROM mailbox mb
    WHERE mb.sender = messages.sender
      AND mb.recipient = messages.recipient
      AND mb.body = messages.content
      AND mb.task_id IS messages.task_id
    LIMIT 1
)
WHERE type = 'chat';

-- Insert any mailbox-only rows (the deliver() bug where messages were not logged to chat)
INSERT INTO messages (timestamp, sender, recipient, content, type, task_id, delivered_at, seen_at, processed_at)
SELECT mb.created_at, mb.sender, mb.recipient, mb.body, 'chat', mb.task_id, mb.delivered_at, mb.seen_at, mb.processed_at
FROM mailbox mb
WHERE NOT EXISTS (
    SELECT 1 FROM messages m
    WHERE m.sender = mb.sender
      AND m.recipient = mb.recipient
      AND m.content = mb.body
      AND m.task_id IS mb.task_id
);

-- Create indexes for efficient unread queries (replicate mailbox indexes)
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

-- Drop the mailbox table
DROP TABLE IF EXISTS mailbox;
