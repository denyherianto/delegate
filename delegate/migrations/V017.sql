-- V17: Add retry_after field for WORKTREE_ERROR exponential backoff
-- Stores a Unix timestamp (float). NULL means no delay is scheduled.
ALTER TABLE tasks ADD COLUMN retry_after REAL;
