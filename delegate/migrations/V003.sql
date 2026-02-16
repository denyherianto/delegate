-- V3: mailbox table
CREATE TABLE IF NOT EXISTS mailbox (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sender         TEXT    NOT NULL,
    recipient      TEXT    NOT NULL,
    body           TEXT    NOT NULL,
    created_at     TEXT    NOT NULL,
    delivered_at   TEXT,
    seen_at        TEXT,
    processed_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_mailbox_recipient_unread
    ON mailbox(recipient, delivered_at)
    WHERE processed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mailbox_sender
    ON mailbox(sender);
CREATE INDEX IF NOT EXISTS idx_mailbox_undelivered
    ON mailbox(id)
    WHERE delivered_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mailbox_recipient_processed
    ON mailbox(recipient, processed_at)
    WHERE processed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mailbox_recipient_sender_processed
    ON mailbox(recipient, sender, processed_at)
    WHERE processed_at IS NOT NULL;
