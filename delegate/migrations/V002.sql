-- V2: tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT    NOT NULL,
    description      TEXT    NOT NULL DEFAULT '',
    status           TEXT    NOT NULL DEFAULT 'todo',
    dri              TEXT    NOT NULL DEFAULT '',
    assignee         TEXT    NOT NULL DEFAULT '',
    project          TEXT    NOT NULL DEFAULT '',
    priority         TEXT    NOT NULL DEFAULT 'medium',
    repo             TEXT    NOT NULL DEFAULT '',
    tags             TEXT    NOT NULL DEFAULT '[]',
    created_at       TEXT    NOT NULL,
    updated_at       TEXT    NOT NULL,
    completed_at     TEXT    NOT NULL DEFAULT '',
    depends_on       TEXT    NOT NULL DEFAULT '[]',
    branch           TEXT    NOT NULL DEFAULT '',
    base_sha         TEXT    NOT NULL DEFAULT '',
    commits          TEXT    NOT NULL DEFAULT '[]',
    rejection_reason TEXT    NOT NULL DEFAULT '',
    approval_status  TEXT    NOT NULL DEFAULT '',
    merge_base       TEXT    NOT NULL DEFAULT '',
    merge_tip        TEXT    NOT NULL DEFAULT '',
    attachments      TEXT    NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_tasks_status
    ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee
    ON tasks(assignee);
CREATE INDEX IF NOT EXISTS idx_tasks_dri
    ON tasks(dri);
CREATE INDEX IF NOT EXISTS idx_tasks_repo
    ON tasks(repo);
CREATE INDEX IF NOT EXISTS idx_tasks_branch
    ON tasks(branch);
CREATE INDEX IF NOT EXISTS idx_tasks_project
    ON tasks(project);
