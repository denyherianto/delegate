"""Unit tests for delegate.paths — verify the protected/ layout."""

from pathlib import Path

from delegate.paths import (
    protected_dir,
    protected_team_dir,
    global_db_path,
    daemon_pid_path,
    config_path,
    network_config_path,
    members_dir,
    member_path,
    roster_path,
    team_id_path,
    repos_config_path,
    teams_dir,
    team_dir,
    repos_dir,
    agents_dir,
    shared_dir,
    ensure_protected,
    ensure_protected_team,
)


class TestProtectedPaths:
    """All infrastructure paths live under protected/."""

    def test_protected_dir(self, tmp_path):
        assert protected_dir(tmp_path) == tmp_path / "protected"

    def test_protected_team_dir(self, tmp_path):
        assert protected_team_dir(tmp_path, "alpha") == tmp_path / "protected" / "projects" / "alpha"

    def test_global_db_path(self, tmp_path):
        assert global_db_path(tmp_path) == tmp_path / "protected" / "db.sqlite"

    def test_daemon_pid_path(self, tmp_path):
        assert daemon_pid_path(tmp_path) == tmp_path / "protected" / "daemon.pid"

    def test_config_path(self, tmp_path):
        assert config_path(tmp_path) == tmp_path / "protected" / "config.yaml"

    def test_network_config_path(self, tmp_path):
        assert network_config_path(tmp_path) == tmp_path / "protected" / "network.yaml"

    def test_members_dir(self, tmp_path):
        assert members_dir(tmp_path) == tmp_path / "protected" / "members"

    def test_member_path(self, tmp_path):
        assert member_path(tmp_path, "alice") == tmp_path / "protected" / "members" / "alice.yaml"

    def test_roster_path(self, tmp_path):
        assert roster_path(tmp_path, "alpha") == tmp_path / "protected" / "projects" / "alpha" / "roster.md"

    def test_team_id_path(self, tmp_path):
        assert team_id_path(tmp_path, "alpha") == tmp_path / "protected" / "projects" / "alpha" / "team_id"

    def test_repos_config_path(self, tmp_path):
        assert repos_config_path(tmp_path, "alpha") == tmp_path / "protected" / "projects" / "alpha" / "repos.yaml"


class TestWorkingDataPaths:
    """Working data paths live under projects/ (previously teams/)."""

    def test_teams_dir(self, tmp_path):
        assert teams_dir(tmp_path) == tmp_path / "projects"

    def test_team_dir(self, tmp_path):
        assert team_dir(tmp_path, "alpha") == tmp_path / "projects" / "alpha"

    def test_repos_dir(self, tmp_path):
        assert repos_dir(tmp_path, "alpha") == tmp_path / "projects" / "alpha" / "repos"

    def test_agents_dir(self, tmp_path):
        assert agents_dir(tmp_path, "alpha") == tmp_path / "projects" / "alpha" / "agents"

    def test_shared_dir(self, tmp_path):
        assert shared_dir(tmp_path, "alpha") == tmp_path / "projects" / "alpha" / "shared"


class TestEnsureHelpers:
    """ensure_protected() and ensure_protected_team() create directories."""

    def test_ensure_protected(self, tmp_path):
        ensure_protected(tmp_path)
        assert protected_dir(tmp_path).is_dir()
        assert (protected_dir(tmp_path) / "projects").is_dir()
        assert members_dir(tmp_path).is_dir()

    def test_ensure_protected_team(self, tmp_path):
        ensure_protected(tmp_path)
        ensure_protected_team(tmp_path, "alpha")
        assert protected_team_dir(tmp_path, "alpha").is_dir()

    def test_ensure_protected_idempotent(self, tmp_path):
        ensure_protected(tmp_path)
        ensure_protected(tmp_path)  # should not raise
        assert protected_dir(tmp_path).is_dir()


class TestTeamsToProjectsMigration:
    """Tests for the teams→projects filesystem migration."""

    def test_fresh_install_uses_projects_dirs(self, tmp_path):
        """Fresh install creates projects/ and project_map.json, not teams/."""
        from delegate.paths import (
            invalidate_team_map_cache,
            register_team_path,
            _team_map_path,
        )
        invalidate_team_map_cache(tmp_path)

        # On a fresh install, teams_dir() points to projects/
        assert teams_dir(tmp_path) == tmp_path / "projects"

        # ensure_protected creates projects/ not teams/
        ensure_protected(tmp_path)
        assert (protected_dir(tmp_path) / "projects").is_dir()
        assert not (protected_dir(tmp_path) / "teams").is_dir()

        # team map file is project_map.json
        register_team_path(tmp_path, "myteam", "abc123")
        assert _team_map_path(tmp_path) == protected_dir(tmp_path) / "project_map.json"
        assert (protected_dir(tmp_path) / "project_map.json").exists()
        assert not (protected_dir(tmp_path) / "team_map.json").exists()

        invalidate_team_map_cache(tmp_path)

    def test_migration_renames_teams_to_projects(self, tmp_path):
        """Migration renames teams/ -> projects/, protected/teams/ -> protected/projects/,
        and team_map.json -> project_map.json."""
        import json
        from delegate.migrations.migrate_teams_to_projects import migrate_teams_to_projects

        # Set up an old-style installation layout
        protected = tmp_path / "protected"
        protected.mkdir()
        old_teams_dir = protected / "teams"
        old_teams_dir.mkdir()
        old_map = protected / "team_map.json"
        old_map.write_text(json.dumps({"myteam": "abc123uuid"}))

        old_working = tmp_path / "teams"
        old_working.mkdir()
        (old_working / "abc123uuid").mkdir()  # UUID-named subdir

        # Run migration
        migrate_teams_to_projects(tmp_path)

        # Directories renamed
        assert not (protected / "teams").exists()
        assert (protected / "projects").is_dir()
        assert not (tmp_path / "teams").exists()
        assert (tmp_path / "projects").is_dir()
        assert (tmp_path / "projects" / "abc123uuid").is_dir()

        # Config file renamed
        assert not old_map.exists()
        assert (protected / "project_map.json").exists()
        assert json.loads((protected / "project_map.json").read_text()) == {"myteam": "abc123uuid"}

        # Sentinel written
        assert (protected / ".migrated_projects").exists()

    def test_migration_idempotent(self, tmp_path):
        """Running migration twice is a no-op (sentinel prevents double-run)."""
        import json
        from delegate.migrations.migrate_teams_to_projects import migrate_teams_to_projects

        # Set up old layout
        protected = tmp_path / "protected"
        protected.mkdir()
        (protected / "teams").mkdir()
        (protected / "team_map.json").write_text(json.dumps({"t": "u"}))
        (tmp_path / "teams").mkdir()

        # First run: migrates everything
        migrate_teams_to_projects(tmp_path)
        assert (protected / ".migrated_projects").exists()
        assert (protected / "projects").is_dir()
        assert (protected / "project_map.json").exists()

        # Modify files after migration to verify second run doesn't touch them
        (protected / "project_map.json").write_text(json.dumps({"t": "u", "extra": "data"}))

        # Second run: sentinel present, no changes made
        migrate_teams_to_projects(tmp_path)
        data = json.loads((protected / "project_map.json").read_text())
        assert data == {"t": "u", "extra": "data"}, "Second run must not overwrite project_map.json"
