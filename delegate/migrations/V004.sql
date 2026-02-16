-- V4: task_id on mailbox + messages
ALTER TABLE mailbox ADD COLUMN task_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_mailbox_task_id
    ON mailbox(task_id);
ALTER TABLE messages ADD COLUMN task_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_messages_task_id
    ON messages(task_id);
