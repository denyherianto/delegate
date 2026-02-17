"""Tests for the /teams/{team}/cost-summary endpoint in delegate/web.py.

These tests verify that cost summaries correctly filter by team_uuid rather
than team name, ensuring the endpoint returns actual cost data.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from delegate.web import create_app
from delegate.chat import start_session, end_session
from delegate.task import create_task
from delegate.db import get_connection
from delegate.paths import resolve_team_uuid

TEAM = "testteam"


@pytest.fixture
def client(tmp_team):
    """Create a FastAPI test client using a bootstrapped team directory."""
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


def _create_sessions_with_costs(hc_home, team_name, sessions_data):
    """Create sessions with specified costs for testing.

    sessions_data: list of dicts with keys: agent, task_id, cost_usd, started_at
    """
    team_uuid = resolve_team_uuid(hc_home, team_name)

    for session in sessions_data:
        # Start session
        session_id = start_session(
            hc_home,
            team_name,
            session["agent"],
            session.get("task_id")
        )

        # Update session with cost and started_at
        conn = get_connection(hc_home, team_name)
        conn.execute(
            """UPDATE sessions
               SET cost_usd = ?, started_at = ?
               WHERE id = ?""",
            (session["cost_usd"], session["started_at"], session_id)
        )
        conn.commit()
        conn.close()


class TestCostSummaryEndpoint:
    def test_cost_summary_returns_nonzero_with_sessions(self, tmp_team, client):
        """Verify cost summary returns actual costs when sessions exist."""
        # Create a task
        task = create_task(tmp_team, TEAM, title="Test Task", assignee="alice")

        # Create sessions with costs for today
        today = datetime.now(timezone.utc).isoformat()
        _create_sessions_with_costs(tmp_team, TEAM, [
            {
                "agent": "alice",
                "task_id": task["id"],
                "cost_usd": 0.50,
                "started_at": today
            },
            {
                "agent": "bob",
                "task_id": task["id"],
                "cost_usd": 0.75,
                "started_at": today
            }
        ])

        # Call cost-summary endpoint
        resp = client.get(f"/teams/{TEAM}/cost-summary")
        assert resp.status_code == 200
        data = resp.json()

        # Verify today section has non-zero cost
        assert data["today"]["total_cost_usd"] > 0
        assert data["today"]["total_cost_usd"] == 1.25
        assert data["today"]["task_count"] == 1

    def test_cost_summary_today_vs_week(self, tmp_team, client):
        """Verify today and week sections aggregate correctly."""
        task1 = create_task(tmp_team, TEAM, title="Task 1", assignee="alice")
        task2 = create_task(tmp_team, TEAM, title="Task 2", assignee="bob")

        now = datetime.now(timezone.utc)
        today = now.isoformat()
        # Create a date from last week (8 days ago)
        last_week = (now - timedelta(days=8)).isoformat()

        _create_sessions_with_costs(tmp_team, TEAM, [
            # Today sessions
            {"agent": "alice", "task_id": task1["id"], "cost_usd": 1.00, "started_at": today},
            # Last week
            {"agent": "bob", "task_id": task2["id"], "cost_usd": 0.50, "started_at": last_week},
        ])

        resp = client.get(f"/teams/{TEAM}/cost-summary")
        assert resp.status_code == 200
        data = resp.json()

        # Today should have only task1 at $1.00
        assert data["today"]["total_cost_usd"] == 1.00
        assert data["today"]["task_count"] == 1

        # This week should also only have task1 (task2 is from last week)
        assert data["this_week"]["total_cost_usd"] == 1.00
        assert data["this_week"]["task_count"] == 1

    def test_cost_summary_top_tasks(self, tmp_team, client):
        """Verify top tasks section returns correct task costs."""
        task1 = create_task(tmp_team, TEAM, title="Expensive Task", assignee="alice")
        task2 = create_task(tmp_team, TEAM, title="Cheap Task", assignee="bob")

        today = datetime.now(timezone.utc).isoformat()

        _create_sessions_with_costs(tmp_team, TEAM, [
            # Multiple sessions for task1
            {"agent": "alice", "task_id": task1["id"], "cost_usd": 2.00, "started_at": today},
            {"agent": "alice", "task_id": task1["id"], "cost_usd": 1.50, "started_at": today},
            # One session for task2
            {"agent": "bob", "task_id": task2["id"], "cost_usd": 0.25, "started_at": today},
        ])

        resp = client.get(f"/teams/{TEAM}/cost-summary")
        assert resp.status_code == 200
        data = resp.json()

        # Top tasks should be ordered by cost
        top_tasks = data["top_tasks"]
        assert len(top_tasks) == 2

        # First task should be the expensive one
        assert top_tasks[0]["task_id"] == task1["id"]
        assert top_tasks[0]["cost_usd"] == 3.50
        assert top_tasks[0]["title"] == "Expensive Task"

        # Second task should be the cheap one
        assert top_tasks[1]["task_id"] == task2["id"]
        assert top_tasks[1]["cost_usd"] == 0.25
        assert top_tasks[1]["title"] == "Cheap Task"

    def test_cost_summary_empty_when_no_sessions(self, tmp_team, client):
        """Verify endpoint returns zeros when no sessions exist."""
        resp = client.get(f"/teams/{TEAM}/cost-summary")
        assert resp.status_code == 200
        data = resp.json()

        assert data["today"]["total_cost_usd"] == 0.0
        assert data["today"]["task_count"] == 0
        assert data["this_week"]["total_cost_usd"] == 0.0
        assert data["this_week"]["task_count"] == 0
        assert len(data["top_tasks"]) == 0

    def test_cost_summary_uses_local_timezone_not_utc(self, tmp_team):
        """Verify 'today' uses local calendar day, not UTC calendar day.

        Scenario: local timezone is UTC-8. Mock local time to Tuesday
        2026-02-10 00:30 local (= 08:30 UTC Tuesday).

        - Session A: stored at 2026-02-10T07:00:00+00:00 (= Monday 23:00 local)
          -> should appear in 'this week' but NOT 'today'
        - Session B: stored at 2026-02-10T09:00:00+00:00 (= Tuesday 01:00 local)
          -> should appear in both 'today' and 'this week'

        With UTC-only logic: midnight_today = 2026-02-10T00:00:00Z, so Session A
        (07:00 UTC) would incorrectly appear in 'today'. With local timezone
        logic: midnight_today_utc = 2026-02-10T08:00:00Z, correctly excluding
        Session A from 'today'.
        """
        # UTC-8 offset
        local_tz = timezone(timedelta(hours=-8))

        # Tuesday 2026-02-10 00:30 local (UTC-8) = 2026-02-10 08:30 UTC
        mocked_local_now = datetime(2026, 2, 10, 0, 30, 0, tzinfo=local_tz)

        task1 = create_task(tmp_team, TEAM, title="Monday Night Task", assignee="alice")
        task2 = create_task(tmp_team, TEAM, title="Tuesday Task", assignee="bob")

        # Session A: Monday 23:00 local = 2026-02-10 07:00 UTC
        session_a_utc = "2026-02-10T07:00:00+00:00"
        # Session B: Tuesday 01:00 local = 2026-02-10 09:00 UTC
        session_b_utc = "2026-02-10T09:00:00+00:00"

        _create_sessions_with_costs(tmp_team, TEAM, [
            {"agent": "alice", "task_id": task1["id"], "cost_usd": 1.00, "started_at": session_a_utc},
            {"agent": "bob", "task_id": task2["id"], "cost_usd": 2.00, "started_at": session_b_utc},
        ])

        # Patch datetime.now().astimezone() in delegate.web to return our mocked local time
        mock_dt = MagicMock(wraps=datetime)
        mock_dt.now = MagicMock(return_value=MagicMock(astimezone=MagicMock(return_value=mocked_local_now)))

        app = create_app(hc_home=tmp_team)
        test_client = TestClient(app)

        with patch("delegate.web.datetime", mock_dt):
            resp = test_client.get(f"/teams/{TEAM}/cost-summary")

        assert resp.status_code == 200
        data = resp.json()

        # 'today' (Tuesday local) should only include Session B ($2.00)
        assert data["today"]["total_cost_usd"] == 2.00, (
            "Session A is Monday local time and must not appear in 'today'"
        )
        assert data["today"]["task_count"] == 1

        # 'this week' (Monday 00:00 local = 08:00 UTC onwards) includes both sessions
        assert data["this_week"]["total_cost_usd"] == 3.00, (
            "Both sessions fall within the current local week"
        )
        assert data["this_week"]["task_count"] == 2
