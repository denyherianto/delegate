"""Tests for the POST /projects endpoint in delegate/web.py.

Covers tilde expansion in repo_path and related validation behavior,
agent name generation, upfront validation, and rollback on failure.
"""

import os
import re
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from delegate.web import create_app


@pytest.fixture
def client(tmp_team):
    """Create a FastAPI test client using a bootstrapped team directory."""
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


class TestCreateProjectTildeExpansion:
    def test_tilde_path_accepted_when_directory_exists(self, tmp_team, tmp_path, client, monkeypatch):
        """A repo_path starting with ~ is expanded correctly to the home directory.

        We redirect HOME to tmp_path so that Path('~/my-repo').expanduser()
        resolves to a directory we can actually create in the sandbox.
        """
        repo_dir = tmp_path / "my-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()  # Must look like a git repo

        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("delegate.repo.register_repo"), \
             patch("delegate.activity.broadcast_teams_refresh"):
            resp = client.post(
                "/projects",
                json={
                    "name": "tilde-test",
                    "repo_path": "~/my-repo",
                    "agent_count": 1,
                    "model": "sonnet",
                },
            )

        # Should succeed, not fail with "does not exist"
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["name"] == "tilde-test"
        assert data["status"] == "created"

    def test_tilde_path_error_shows_original_path(self, tmp_team, client):
        """When a ~ path doesn't exist, the error message shows the tilde form."""
        resp = client.post(
            "/projects",
            json={
                "name": "bad-tilde-proj",
                "repo_path": "~/nonexistent-repo-T0088",
                "agent_count": 1,
                "model": "sonnet",
            },
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        # Error should show the original tilde path, not the expanded path
        assert "~/nonexistent-repo-T0088" in detail
        assert "does not exist" in detail

    def test_absolute_path_still_works(self, tmp_team, tmp_path, client):
        """Absolute paths without tilde continue to work as before."""
        repo_dir = tmp_path / "abs-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()  # Must look like a git repo

        with patch("delegate.repo.register_repo"), \
             patch("delegate.activity.broadcast_teams_refresh"):
            resp = client.post(
                "/projects",
                json={
                    "name": "abs-test",
                    "repo_path": str(repo_dir),
                    "agent_count": 1,
                    "model": "sonnet",
                },
            )

        assert resp.status_code == 200, resp.text
        assert resp.json()["name"] == "abs-test"


class TestAgentNameGeneration:
    def test_agent_names_are_not_agent_n_format(self, tmp_team, tmp_path, client, monkeypatch):
        """Agents created via POST /projects use friendly names, not 'agent-N' format."""
        from delegate.paths import agents_dir

        repo_dir = tmp_path / "my-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()  # Must look like a git repo

        with patch("delegate.repo.register_repo"), \
             patch("delegate.activity.broadcast_teams_refresh"):
            resp = client.post(
                "/projects",
                json={
                    "name": "friendly-names-test",
                    "repo_path": str(repo_dir),
                    "agent_count": 2,
                    "model": "sonnet",
                },
            )

        assert resp.status_code == 200, resp.text

        # Check that none of the created worker agents have "agent-N" names
        ad = agents_dir(tmp_team, "friendly-names-test")
        agent_names = [p.name for p in ad.iterdir() if p.is_dir()]
        # Filter out the manager ("delegate")
        worker_names = [n for n in agent_names if n != "delegate"]
        assert len(worker_names) == 2
        for name in worker_names:
            assert not re.match(r"^agent-\d+$", name), (
                f"Agent name '{name}' looks like a hardcoded name, expected a friendly name"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_git_repo(path: Path) -> Path:
    """Create a minimal git repository at *path*."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=str(path), capture_output=True, check=True,
    )
    return path


# ---------------------------------------------------------------------------
# Upfront validation tests
# ---------------------------------------------------------------------------

class TestCreateProjectValidation:
    """Validation must reject bad input BEFORE creating any state."""

    def test_non_git_directory_rejected(self, tmp_path, client):
        """A directory without .git/ is rejected with 400."""
        repo_dir = tmp_path / "not-a-repo"
        repo_dir.mkdir()
        # No .git/ created

        resp = client.post("/projects", json={
            "name": "no-git-test",
            "repo_path": str(repo_dir),
            "agent_count": 1,
            "model": "sonnet",
        })
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert ".git" in detail or "git repository" in detail.lower()

    def test_non_git_dir_leaves_no_team_state(self, tmp_team, tmp_path, client):
        """Rejecting a non-git dir must NOT create team directories or DB rows."""
        from delegate.db import get_connection
        from delegate.paths import team_dir

        repo_dir = tmp_path / "plain-dir"
        repo_dir.mkdir()

        resp = client.post("/projects", json={
            "name": "ghost-proj",
            "repo_path": str(repo_dir),
            "agent_count": 1,
            "model": "sonnet",
        })
        assert resp.status_code == 400

        # Team directory must NOT exist
        td = team_dir(tmp_team, "ghost-proj")
        assert not td.exists(), f"Team directory was created despite validation failure: {td}"

        # DB row must NOT exist
        conn = get_connection(tmp_team)
        row = conn.execute("SELECT 1 FROM projects WHERE name = ?", ("ghost-proj",)).fetchone()
        conn.close()
        assert row is None, "DB row was created despite validation failure"

    def test_duplicate_name_rejected(self, tmp_team, tmp_path, client):
        """Creating a project with a name that already exists returns 409."""
        from delegate.db import get_connection
        from tests.conftest import SAMPLE_TEAM_NAME

        resp = client.post("/projects", json={
            "name": SAMPLE_TEAM_NAME,
            "repo_path": str(tmp_path),
            "agent_count": 1,
            "model": "sonnet",
        })
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    def test_nonexistent_path_rejected(self, client):
        """A path that doesn't exist at all is rejected with 400."""
        resp = client.post("/projects", json={
            "name": "bad-path-proj",
            "repo_path": "/no/such/path/xyz123",
            "agent_count": 1,
            "model": "sonnet",
        })
        assert resp.status_code == 400
        assert "does not exist" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Rollback tests
# ---------------------------------------------------------------------------

class TestCreateProjectRollback:
    """If a post-bootstrap step fails, partial state must be cleaned up."""

    def test_register_repo_failure_rolls_back(self, tmp_team, tmp_path, client):
        """When register_repo raises after bootstrap, the team is cleaned up."""
        from delegate.db import get_connection
        from delegate.paths import team_dir

        repo_dir = tmp_path / "rollback-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()  # Pass upfront validation

        # Make register_repo fail (e.g. permission error, symlink issue)
        with patch("delegate.repo.register_repo", side_effect=RuntimeError("simulated failure")), \
             patch("delegate.activity.broadcast_teams_refresh"):
            resp = client.post("/projects", json={
                "name": "rollback-test",
                "repo_path": str(repo_dir),
                "agent_count": 1,
                "model": "sonnet",
            })

        assert resp.status_code == 500
        assert "simulated failure" in resp.json()["detail"]

        # Team directory must be cleaned up
        td = team_dir(tmp_team, "rollback-test")
        assert not td.exists(), f"Team directory not cleaned up after failure: {td}"

        # DB row must be cleaned up
        conn = get_connection(tmp_team)
        row = conn.execute("SELECT 1 FROM projects WHERE name = ?", ("rollback-test",)).fetchone()
        conn.close()
        assert row is None, "DB row not cleaned up after failure"

    def test_successful_creation_with_real_git_repo(self, tmp_team, tmp_path, client):
        """Full end-to-end: real git repo → project created successfully."""
        from delegate.db import get_connection
        from delegate.paths import team_dir

        repo_dir = _make_git_repo(tmp_path / "real-repo")

        with patch("delegate.activity.broadcast_teams_refresh"):
            resp = client.post("/projects", json={
                "name": "e2e-test",
                "repo_path": str(repo_dir),
                "agent_count": 1,
                "model": "sonnet",
            })

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["name"] == "e2e-test"
        assert data["status"] == "created"

        # Team directory exists
        td = team_dir(tmp_team, "e2e-test")
        assert td.is_dir()

        # DB row exists
        conn = get_connection(tmp_team)
        row = conn.execute("SELECT 1 FROM projects WHERE name = ?", ("e2e-test",)).fetchone()
        conn.close()
        assert row is not None
