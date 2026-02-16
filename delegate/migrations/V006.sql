-- V6: cache token columns on sessions
ALTER TABLE sessions ADD COLUMN cache_read_tokens INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN cache_write_tokens INTEGER DEFAULT 0;
