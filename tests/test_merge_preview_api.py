"""Tests for merge-preview API endpoint (global /api/tasks/{id}/merge-preview)."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from delegate.task import create_task, change_status, get_task, set_task_branch
from delegate.web import create_app

TEAM = "testteam"


@pytest.fixture
def client(tmp_team):
    """Create a FastAPI test client with a bootstrapped team root."""
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


@pytest.fixture
def task_with_branch(tmp_team):
    """Create a task with a branch set."""
    task = create_task(tmp_team, TEAM, title="Feature X", assignee="alice")
    set_task_branch(tmp_team, TEAM, task["id"], "delegate/abc123/team/T0001")
    return get_task(tmp_team, TEAM, task["id"])


@pytest.fixture
def task_without_branch(tmp_team):
    """Create a task without a branch set."""
    task = create_task(tmp_team, TEAM, title="No Branch Task", assignee="alice")
    return get_task(tmp_team, TEAM, task["id"])


# ---------------------------------------------------------------------------
# GET /api/tasks/{task_id}/merge-preview (global endpoint)
# ---------------------------------------------------------------------------

class TestMergePreviewAPI:
    def test_returns_correct_format_with_branch(self, client, task_with_branch, tmp_team):
        """Endpoint returns {task_id, branch, diff} format."""
        with patch('delegate.web._get_merge_preview') as mock_preview:
            mock_preview.return_value = {"_default": "diff content"}

            resp = client.get(f"/api/tasks/{task_with_branch['id']}/merge-preview")
            assert resp.status_code == 200
            data = resp.json()

            # Verify structure matches team-scoped endpoint
            assert "task_id" in data
            assert "branch" in data
            assert "diff" in data

            # Verify values
            assert data["task_id"] == task_with_branch["id"]
            assert data["branch"] == "delegate/abc123/team/T0001"
            assert data["diff"] == {"_default": "diff content"}

    def test_returns_empty_branch_when_not_set(self, client, task_without_branch, tmp_team):
        """Task without branch returns empty string for branch field."""
        with patch('delegate.web._get_merge_preview') as mock_preview:
            mock_preview.return_value = {"_default": "(no branch set)"}

            resp = client.get(f"/api/tasks/{task_without_branch['id']}/merge-preview")
            assert resp.status_code == 200
            data = resp.json()

            assert data["task_id"] == task_without_branch["id"]
            assert data["branch"] == ""
            assert data["diff"] == {"_default": "(no branch set)"}

    def test_returns_404_for_nonexistent_task(self, client):
        """Endpoint returns 404 for nonexistent task."""
        resp = client.get(f"/api/tasks/9999/merge-preview")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_handles_multi_repo_diff(self, client, task_with_branch, tmp_team):
        """Endpoint handles multi-repo diffs correctly."""
        with patch('delegate.web._get_merge_preview') as mock_preview:
            mock_preview.return_value = {
                "repo1": "diff for repo1",
                "repo2": "diff for repo2"
            }

            resp = client.get(f"/api/tasks/{task_with_branch['id']}/merge-preview")
            assert resp.status_code == 200
            data = resp.json()

            assert data["diff"] == {
                "repo1": "diff for repo1",
                "repo2": "diff for repo2"
            }

