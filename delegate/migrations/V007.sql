-- V7: merge failure tracking
ALTER TABLE tasks ADD COLUMN status_detail TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN merge_attempts INTEGER NOT NULL DEFAULT 0;
