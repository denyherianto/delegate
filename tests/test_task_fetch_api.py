"""Tests for GET /api/tasks/{task_id} — single-task fetch endpoint.

Verifies:
- Returns the task with a 'team' field
- Returns 404 for non-existent task IDs
- Route is registered before /api/tasks/{task_id}/stats so FastAPI
  doesn't accidentally route /api/tasks/42 to the stats endpoint
"""

import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from delegate.task import create_task
from delegate.web import create_app

TEAM = "testteam"


@pytest.fixture
def client(tmp_team):
    """Create a FastAPI test client with a bootstrapped team root."""
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


@pytest.fixture
def sample_task(tmp_team):
    """Create a task for use in tests."""
    return create_task(tmp_team, TEAM, title="Fix the loading bug", assignee="alice")


# ---------------------------------------------------------------------------
# GET /api/tasks/{task_id}
# ---------------------------------------------------------------------------


class TestGetTaskGlobal:
    def test_returns_task_by_id(self, client, sample_task):
        """Endpoint returns the correct task object."""
        resp = client.get(f"/api/tasks/{sample_task['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sample_task["id"]
        assert data["title"] == "Fix the loading bug"

    def test_response_includes_team_field(self, client, sample_task):
        """Response includes the 'team' field identifying which team owns the task."""
        resp = client.get(f"/api/tasks/{sample_task['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "team" in data
        assert data["team"] == TEAM

    def test_response_includes_standard_task_fields(self, client, sample_task):
        """Response contains expected task fields."""
        resp = client.get(f"/api/tasks/{sample_task['id']}")
        data = resp.json()
        assert "id" in data
        assert "title" in data
        assert "status" in data
        assert "created_at" in data

    def test_nonexistent_task_returns_404(self, client):
        """Requesting a task ID that doesn't exist returns 404."""
        resp = client.get("/api/tasks/9999")
        assert resp.status_code == 404
        data = resp.json()
        assert "not found" in data["detail"].lower()

    def test_404_detail_mentions_task_id(self, client):
        """404 error message includes the requested task ID."""
        resp = client.get("/api/tasks/12345")
        assert resp.status_code == 404
        assert "12345" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Route ordering: /api/tasks/{task_id} must not shadow sub-routes
# ---------------------------------------------------------------------------


class TestRouteOrdering:
    def test_stats_route_still_reachable(self, client, sample_task):
        """GET /api/tasks/{task_id}/stats still works — not swallowed by the new route."""
        resp = client.get(f"/api/tasks/{sample_task['id']}/stats")
        # Either 200 (stats found) or 404 (no sessions yet) is fine —
        # the key check is that it's NOT a 422 Unprocessable Entity, which
        # would indicate FastAPI matched the wrong route.
        assert resp.status_code in (200, 404)
        assert resp.status_code != 422

    def test_activity_route_still_reachable(self, client, sample_task):
        """GET /api/tasks/{task_id}/activity still works — not swallowed by the new route."""
        resp = client.get(f"/api/tasks/{sample_task['id']}/activity")
        assert resp.status_code in (200, 404)
        assert resp.status_code != 422

    def test_diff_route_still_reachable(self, client, sample_task):
        """GET /api/tasks/{task_id}/diff still works — not swallowed by the new route."""
        resp = client.get(f"/api/tasks/{sample_task['id']}/diff")
        assert resp.status_code in (200, 404)
        assert resp.status_code != 422

    def test_task_endpoint_returns_json_not_stats(self, client, sample_task):
        """GET /api/tasks/{task_id} returns the task object, not the stats object."""
        resp = client.get(f"/api/tasks/{sample_task['id']}")
        data = resp.json()
        # Task object has 'title', stats object has 'elapsed_seconds'
        assert "title" in data
        assert "elapsed_seconds" not in data

# ---------------------------------------------------------------------------
# Exception logging: unexpected errors are logged, not silently swallowed
# ---------------------------------------------------------------------------


class TestUnexpectedExceptionLogging:
    """Verify that unexpected exceptions are logged (not silently swallowed) across
    all global task endpoints.  Each endpoint must still return 404 so the
    cross-team scan can continue, but the error must appear in the log so it
    can be diagnosed.
    """

    def test_get_task_global_logs_unexpected_exception(self, tmp_team, caplog):
        """GET /api/tasks/{task_id}: unexpected _get_task exception is logged."""
        app = create_app(hc_home=tmp_team)
        client = TestClient(app)

        with patch("delegate.web._get_task", side_effect=ValueError("data corruption")):
            with caplog.at_level(logging.ERROR, logger="delegate.web"):
                resp = client.get("/api/tasks/42")

        assert resp.status_code == 404
        assert any("Unexpected error" in r.message for r in caplog.records)
        assert any("get_task_global" in r.message for r in caplog.records)

    def test_get_task_stats_global_logs_unexpected_exception(self, tmp_team, caplog):
        """GET /api/tasks/{task_id}/stats: unexpected _get_task exception is logged."""
        app = create_app(hc_home=tmp_team)
        client = TestClient(app)

        with patch("delegate.web._get_task", side_effect=ValueError("data corruption")):
            with caplog.at_level(logging.ERROR, logger="delegate.web"):
                resp = client.get("/api/tasks/42/stats")

        assert resp.status_code == 404
        assert any("Unexpected error" in r.message for r in caplog.records)
        assert any("get_task_stats_global" in r.message for r in caplog.records)

    def test_get_task_diff_global_logs_unexpected_exception(self, tmp_team, caplog):
        """GET /api/tasks/{task_id}/diff: unexpected _get_task exception is logged."""
        app = create_app(hc_home=tmp_team)
        client = TestClient(app)

        with patch("delegate.web._get_task", side_effect=ValueError("data corruption")):
            with caplog.at_level(logging.ERROR, logger="delegate.web"):
                resp = client.get("/api/tasks/42/diff")

        assert resp.status_code == 404
        assert any("Unexpected error" in r.message for r in caplog.records)
        assert any("get_task_diff_global" in r.message for r in caplog.records)

    def test_get_task_activity_global_logs_unexpected_exception(self, tmp_team, caplog):
        """GET /api/tasks/{task_id}/activity: unexpected _get_task exception is logged."""
        app = create_app(hc_home=tmp_team)
        client = TestClient(app)

        with patch("delegate.web._get_task", side_effect=ValueError("data corruption")):
            with caplog.at_level(logging.ERROR, logger="delegate.web"):
                resp = client.get("/api/tasks/42/activity")

        assert resp.status_code == 404
        assert any("Unexpected error" in r.message for r in caplog.records)
        assert any("get_task_activity_global" in r.message for r in caplog.records)
