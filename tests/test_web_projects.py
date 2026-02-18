"""Tests for the POST /projects endpoint in delegate/web.py.

Covers tilde expansion in repo_path and related validation behavior.
"""

import os
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
