-- V15: UUID translation tables (team_ids, member_ids)
CREATE TABLE IF NOT EXISTS team_ids (
    uuid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    deleted INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_team_ids_active ON team_ids(name) WHERE deleted = 0;

CREATE TABLE IF NOT EXISTS member_ids (
    uuid TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('agent', 'human')),
    team_uuid TEXT,
    name TEXT NOT NULL,
    deleted INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_member_ids_active
    ON member_ids(kind, team_uuid, name) WHERE deleted = 0;

-- Update teams.team_id to store full UUID (pad existing 6-char values to 32 chars)
UPDATE teams SET team_id = team_id || '00000000000000000000000000' WHERE length(team_id) = 6;
