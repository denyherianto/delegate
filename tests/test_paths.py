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
        assert protected_team_dir(tmp_path, "alpha") == tmp_path / "protected" / "teams" / "alpha"

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
        assert roster_path(tmp_path, "alpha") == tmp_path / "protected" / "teams" / "alpha" / "roster.md"

    def test_team_id_path(self, tmp_path):
        assert team_id_path(tmp_path, "alpha") == tmp_path / "protected" / "teams" / "alpha" / "team_id"

    def test_repos_config_path(self, tmp_path):
        assert repos_config_path(tmp_path, "alpha") == tmp_path / "protected" / "teams" / "alpha" / "repos.yaml"


class TestWorkingDataPaths:
    """Working data paths live under teams/."""

    def test_teams_dir(self, tmp_path):
        assert teams_dir(tmp_path) == tmp_path / "teams"

    def test_team_dir(self, tmp_path):
        assert team_dir(tmp_path, "alpha") == tmp_path / "teams" / "alpha"

    def test_repos_dir(self, tmp_path):
        assert repos_dir(tmp_path, "alpha") == tmp_path / "teams" / "alpha" / "repos"

    def test_agents_dir(self, tmp_path):
        assert agents_dir(tmp_path, "alpha") == tmp_path / "teams" / "alpha" / "agents"

    def test_shared_dir(self, tmp_path):
        assert shared_dir(tmp_path, "alpha") == tmp_path / "teams" / "alpha" / "shared"


class TestEnsureHelpers:
    """ensure_protected() and ensure_protected_team() create directories."""

    def test_ensure_protected(self, tmp_path):
        ensure_protected(tmp_path)
        assert protected_dir(tmp_path).is_dir()
        assert (protected_dir(tmp_path) / "teams").is_dir()
        assert members_dir(tmp_path).is_dir()

    def test_ensure_protected_team(self, tmp_path):
        ensure_protected(tmp_path)
        ensure_protected_team(tmp_path, "alpha")
        assert protected_team_dir(tmp_path, "alpha").is_dir()

    def test_ensure_protected_idempotent(self, tmp_path):
        ensure_protected(tmp_path)
        ensure_protected(tmp_path)  # should not raise
        assert protected_dir(tmp_path).is_dir()
