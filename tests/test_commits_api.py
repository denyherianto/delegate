"""Tests for the GET /api/tasks/{task_id}/commits endpoint."""

import pytest
from fastapi.testclient import TestClient

from delegate.task import create_task
from delegate.web import create_app

TEAM = "testteam"


@pytest.fixture
def client(tmp_team):
    """Create a FastAPI test client with a bootstrapped team."""
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


class TestGlobalCommitsEndpoint:
    """Tests for the global /api/tasks/{task_id}/commits endpoint."""

    def test_commits_endpoint_returns_commit_diffs_key(self, tmp_team, client):
        """The global commits endpoint must return commit_diffs, not commits."""
        # Create a task
        task = create_task(tmp_team, TEAM, title="Test task", assignee="manager")
        task_id = task["id"]

        # Call the global commits endpoint
        resp = client.get(f"/api/tasks/{task_id}/commits")
        assert resp.status_code == 200

        data = resp.json()

        # The key must be "commit_diffs", not "commits"
        assert "commit_diffs" in data, "Response must contain 'commit_diffs' key"
        assert "commits" not in data, "Response must NOT contain 'commits' key (deprecated)"

        # Other expected fields
        assert "task_id" in data
        assert data["task_id"] == task_id
        assert "branch" in data

    def test_commits_endpoint_404_for_nonexistent_task(self, client):
        """The global commits endpoint returns 404 for non-existent tasks."""
        resp = client.get("/api/tasks/99999/commits")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
