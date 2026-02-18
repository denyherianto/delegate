"""Tests for project name validation (T0111).

Covers:
- validate_project_name() unit tests (valid and invalid slugs)
- CLI team add: rejects invalid names before doing any work
- API POST /projects: rejects invalid names with 400
"""

import pytest
from unittest.mock import patch
from pathlib import Path

from click.testing import CliRunner
from fastapi.testclient import TestClient

from delegate.bootstrap import validate_project_name
from delegate.cli import main
from delegate.web import create_app


# ---------------------------------------------------------------------------
# Unit tests for validate_project_name
# ---------------------------------------------------------------------------

class TestValidateProjectName:
    @pytest.mark.parametrize("name", [
        "my-project-2026",
        "my_project",
        "abc",
        "a1b2",
        "project",
        "x",
        "1project",
        "my-project_v2",
    ])
    def test_valid_names_pass(self, name):
        """Valid slug names should not raise."""
        validate_project_name(name)  # must not raise

    @pytest.mark.parametrize("name", [
        "my project",       # space
        "MyProject",        # uppercase
        "My-Project",       # uppercase with hyphen
        "-myproject",       # starts with hyphen
        "_myproject",       # starts with underscore
        "",                 # empty
        "my project 2",     # multiple spaces
        "UPPER",            # all uppercase
        "hello world",      # space
        "a/b",              # slash
        "a.b",              # dot
    ])
    def test_invalid_names_raise(self, name):
        """Invalid names should raise ValueError with a helpful message."""
        with pytest.raises(ValueError) as exc_info:
            validate_project_name(name)
        msg = str(exc_info.value)
        assert "lowercase" in msg
        assert "e.g." in msg


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

@pytest.fixture
def runner():
    return CliRunner()


class TestCLITeamAddValidation:
    def test_space_in_name_rejected(self, tmp_path, runner):
        """'delegate team add \"my project\" ...' should fail with a clear error."""
        result = runner.invoke(
            main,
            ["--home", str(tmp_path), "team", "add", "my project",
             "--agents", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code != 0
        output = result.output
        assert "lowercase" in output.lower() or "Error" in output

    def test_uppercase_name_rejected(self, tmp_path, runner):
        """'delegate team add MyProject ...' should fail with a clear error."""
        result = runner.invoke(
            main,
            ["--home", str(tmp_path), "team", "add", "MyProject",
             "--agents", "1", "--repo", str(tmp_path)],
        )
        assert result.exit_code != 0
        assert "lowercase" in result.output.lower() or "Error" in result.output

    def test_valid_hyphenated_name_accepted(self, tmp_path, runner):
        """'delegate team add my-project-2026 ...' should pass name validation."""
        # We only verify it gets past name validation (bootstrap will fail for other reasons
        # since this is a stripped-down tmp_path, but the error won't be about name format).
        with patch("delegate.bootstrap.bootstrap"), \
             patch("delegate.repo.register_repo"), \
             patch("delegate.workflow.register_workflow"), \
             patch("delegate.workflow.get_latest_version", return_value=None):
            result = runner.invoke(
                main,
                ["--home", str(tmp_path), "team", "add", "my-project-2026",
                 "--agents", "1", "--repo", str(tmp_path)],
            )
        # Name validation passes — any failure is from bootstrap internals, not name check
        assert "lowercase" not in result.output.lower()
        assert "Project name must be" not in result.output

    def test_valid_underscore_name_accepted(self, tmp_path, runner):
        """'delegate team add my_project ...' should pass name validation."""
        with patch("delegate.bootstrap.bootstrap"), \
             patch("delegate.repo.register_repo"), \
             patch("delegate.workflow.register_workflow"), \
             patch("delegate.workflow.get_latest_version", return_value=None):
            result = runner.invoke(
                main,
                ["--home", str(tmp_path), "team", "add", "my_project",
                 "--agents", "1", "--repo", str(tmp_path)],
            )
        assert "Project name must be" not in result.output


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_team):
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


class TestAPIProjectNameValidation:
    def test_space_in_name_rejected(self, client):
        """POST /projects with space in name returns 400."""
        resp = client.post("/projects", json={
            "name": "my project",
            "repo_path": "/tmp",
            "agent_count": 1,
            "model": "sonnet",
        })
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "lowercase" in detail

    def test_uppercase_name_rejected(self, client):
        """POST /projects with uppercase name returns 400."""
        resp = client.post("/projects", json={
            "name": "MyProject",
            "repo_path": "/tmp",
            "agent_count": 1,
            "model": "sonnet",
        })
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "lowercase" in detail

    def test_valid_name_passes_validation(self, tmp_path, client):
        """POST /projects with a valid slug passes name validation."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        with patch("delegate.repo.register_repo"), \
             patch("delegate.activity.broadcast_teams_refresh"):
            resp = client.post("/projects", json={
                "name": "my-project-2026",
                "repo_path": str(repo_dir),
                "agent_count": 1,
                "model": "sonnet",
            })
        # Should not be a name-validation 400
        assert resp.status_code != 400 or "lowercase" not in resp.json().get("detail", "")

    def test_valid_underscore_name_passes_validation(self, tmp_path, client):
        """POST /projects with underscore name passes name validation."""
        repo_dir = tmp_path / "repo2"
        repo_dir.mkdir()

        with patch("delegate.repo.register_repo"), \
             patch("delegate.activity.broadcast_teams_refresh"):
            resp = client.post("/projects", json={
                "name": "my_project",
                "repo_path": str(repo_dir),
                "agent_count": 1,
                "model": "sonnet",
            })
        assert resp.status_code != 400 or "lowercase" not in resp.json().get("detail", "")
