"""Tests for the POST /tasks/{id}/reject endpoint in scripts/web.py."""

import pytest
from fastapi.testclient import TestClient

from scripts.web import create_app
from scripts.task import create_task, change_status, assign_task, get_task
from scripts.mailbox import read_inbox


@pytest.fixture
def client(tmp_team):
    """Create a FastAPI test client using a bootstrapped team directory."""
    app = create_app(root=tmp_team)
    return TestClient(app)


def _task_to_needs_merge(root):
    """Create a task and advance it to needs_merge status. Returns task dict."""
    task = create_task(root, title="Feature X")
    assign_task(root, task["id"], "alice")
    change_status(root, task["id"], "in_progress")
    change_status(root, task["id"], "review")
    change_status(root, task["id"], "needs_merge")
    return get_task(root, task["id"])


class TestRejectEndpoint:
    def test_reject_task(self, tmp_team, client):
        task = _task_to_needs_merge(tmp_team)
        resp = client.post(
            f"/tasks/{task['id']}/reject",
            json={"reason": "Code quality issues"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["task_id"] == task["id"]

    def test_reject_updates_status(self, tmp_team, client):
        task = _task_to_needs_merge(tmp_team)
        client.post(
            f"/tasks/{task['id']}/reject",
            json={"reason": "Needs work"},
        )
        updated = get_task(tmp_team, task["id"])
        assert updated["status"] == "rejected"

    def test_reject_stores_reason(self, tmp_team, client):
        task = _task_to_needs_merge(tmp_team)
        client.post(
            f"/tasks/{task['id']}/reject",
            json={"reason": "Missing tests"},
        )
        updated = get_task(tmp_team, task["id"])
        assert updated["rejection_reason"] == "Missing tests"

    def test_reject_sends_notification_to_manager(self, tmp_team, client):
        task = _task_to_needs_merge(tmp_team)
        client.post(
            f"/tasks/{task['id']}/reject",
            json={"reason": "Code quality issues"},
        )
        # Check manager's inbox for notification
        inbox = read_inbox(tmp_team, "manager", unread_only=True)
        assert len(inbox) >= 1

        msg = inbox[0]
        assert msg.recipient == "manager"
        assert "TASK_REJECTED" in msg.body
        assert f"T{task['id']:04d}" in msg.body
        assert "Feature X" in msg.body
        assert "alice" in msg.body
        assert "Code quality issues" in msg.body

    def test_reject_notification_has_suggested_actions(self, tmp_team, client):
        task = _task_to_needs_merge(tmp_team)
        client.post(
            f"/tasks/{task['id']}/reject",
            json={"reason": "Problems found"},
        )
        inbox = read_inbox(tmp_team, "manager", unread_only=True)
        body = inbox[0].body
        assert "Rework" in body
        assert "Reassign" in body
        assert "Discard" in body

    def test_reject_nonexistent_task(self, client):
        resp = client.post("/tasks/999/reject", json={"reason": "Bad"})
        assert resp.status_code == 404

    def test_reject_wrong_status(self, tmp_team, client):
        """Cannot reject a task that isn't in needs_merge status."""
        task = create_task(tmp_team, title="Fresh Task")
        resp = client.post(
            f"/tasks/{task['id']}/reject",
            json={"reason": "Nope"},
        )
        assert resp.status_code == 400
        assert "needs_merge" in resp.json()["detail"].lower()

    def test_reject_no_reason(self, tmp_team, client):
        """Rejecting without a reason should still work."""
        task = _task_to_needs_merge(tmp_team)
        resp = client.post(f"/tasks/{task['id']}/reject", json={})
        assert resp.status_code == 200

        inbox = read_inbox(tmp_team, "manager", unread_only=True)
        body = inbox[0].body
        assert "(no reason provided)" in body
