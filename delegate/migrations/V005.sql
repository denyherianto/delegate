-- V5: reviews + review_comments tables, review_attempt on tasks
ALTER TABLE tasks ADD COLUMN review_attempt INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    INTEGER NOT NULL,
    attempt    INTEGER NOT NULL,
    verdict    TEXT,
    summary    TEXT    NOT NULL DEFAULT '',
    reviewer   TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    decided_at TEXT,
    UNIQUE(task_id, attempt)
);

CREATE INDEX IF NOT EXISTS idx_reviews_task_id
    ON reviews(task_id);

CREATE TABLE IF NOT EXISTS review_comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    INTEGER NOT NULL,
    attempt    INTEGER NOT NULL,
    file       TEXT    NOT NULL,
    line       INTEGER,
    body       TEXT    NOT NULL,
    author     TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_review_comments_task_attempt
    ON review_comments(task_id, attempt);
