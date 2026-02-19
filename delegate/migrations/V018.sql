-- V18: Rename "teams" concept to "projects" in database schema
--
-- Table renames use CREATE + INSERT AS SELECT + DROP + RENAME to avoid
-- any version-specific ALTER TABLE RENAME TABLE edge-cases.
-- Column renames use ALTER TABLE ... RENAME COLUMN (SQLite 3.25+).
-- No data is dropped — all rows are preserved.

-- -----------------------------------------------------------------------
-- 1. Rename `teams` table to `projects`
--    Columns: name, team_id -> project_id, created_at
-- -----------------------------------------------------------------------
CREATE TABLE projects (
    name        TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT INTO projects (name, project_id, created_at)
SELECT name, team_id, created_at FROM teams;

DROP TABLE teams;

-- -----------------------------------------------------------------------
-- 2. Rename `team_ids` table to `project_ids`
--    Columns: uuid, name, deleted, created_at (unchanged)
-- -----------------------------------------------------------------------
CREATE TABLE project_ids (
    uuid       TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    deleted    INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Copy data preserving the unique constraint semantics
INSERT INTO project_ids (uuid, name, deleted, created_at)
SELECT uuid, name, deleted, created_at FROM team_ids;

DROP TABLE team_ids;

-- Recreate the unique index from V015 (index names don't transfer on table drop)
CREATE UNIQUE INDEX IF NOT EXISTS idx_project_ids_active ON project_ids(name) WHERE deleted = 0;

-- -----------------------------------------------------------------------
-- 3. Rename `team` and `team_uuid` columns on data tables
--    ALTER TABLE RENAME COLUMN auto-updates indexes, triggers, views.
-- -----------------------------------------------------------------------

-- messages
ALTER TABLE messages RENAME COLUMN team TO project;
ALTER TABLE messages RENAME COLUMN team_uuid TO project_uuid;

-- sessions
ALTER TABLE sessions RENAME COLUMN team TO project;
ALTER TABLE sessions RENAME COLUMN team_uuid TO project_uuid;

-- tasks
ALTER TABLE tasks RENAME COLUMN team TO project;
ALTER TABLE tasks RENAME COLUMN team_uuid TO project_uuid;

-- task_comments
ALTER TABLE task_comments RENAME COLUMN team TO project;
ALTER TABLE task_comments RENAME COLUMN team_uuid TO project_uuid;

-- reviews
ALTER TABLE reviews RENAME COLUMN team TO project;
ALTER TABLE reviews RENAME COLUMN team_uuid TO project_uuid;

-- review_comments
ALTER TABLE review_comments RENAME COLUMN team TO project;
ALTER TABLE review_comments RENAME COLUMN team_uuid TO project_uuid;
