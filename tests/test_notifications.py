"""Tests for Phase 7: System notifications to manager."""

import pytest
from unittest.mock import patch, MagicMock

from tests.conftest import SAMPLE_TEAM_NAME as TEAM
from delegate.web import _notify_manager_sync


class TestNotifyManagerSync:
    def test_sends_message_to_manager(self, tmp_team):
        """Notification sends a message to the team's manager."""
        from delegate.mailbox import send, read_inbox

        _notify_manager_sync(tmp_team, TEAM, "Test notification body")

        # Manager is the first agent with role=manager
        from delegate.bootstrap import get_member_by_role
        manager = get_member_by_role(tmp_team, TEAM, "manager")
        assert manager is not None

        # Check inbox for the manager
        messages = read_inbox(tmp_team, TEAM, manager)
        assert len(messages) >= 1
        found = any("Test notification body" in m.body for m in messages)
        assert found, f"Expected notification in manager inbox, got: {messages}"

    def test_no_error_without_manager(self, tmp_team):
        """Notification doesn't raise if no manager exists."""
        with patch("delegate.bootstrap.get_member_by_role", return_value=None):
            # Should not raise
            _notify_manager_sync(tmp_team, TEAM, "No manager here")

    def test_graceful_on_send_failure(self, tmp_team):
        """Notification swallows errors from send()."""
        with patch("delegate.mailbox.send", side_effect=Exception("boom")):
            # Should not raise
            _notify_manager_sync(tmp_team, TEAM, "Will fail silently")


class TestTaskCompletionNotification:
    def test_merge_success_notifies_manager(self, tmp_team):
        """Successful merge sends notification to manager."""
        from delegate.task import create_task
        from delegate.bootstrap import get_member_by_role
        from delegate.mailbox import read_inbox

        # Create a task
        task = create_task(tmp_team, TEAM, title="Test task", assignee="alice")

        manager = get_member_by_role(tmp_team, TEAM, "manager")
        assert manager is not None

        # Simulate the notification that would be sent on merge
        from delegate.task import format_task_id
        _notify_manager_sync(
            tmp_team, TEAM,
            f"Task {format_task_id(task['id'])} has been merged successfully.",
        )

        messages = read_inbox(tmp_team, TEAM, manager)
        found = any("merged successfully" in m.body for m in messages)
        assert found

    def test_merge_success_not_redundant(self, tmp_team):
        """Merge success notification doesn't duplicate 'merged successfully'."""
        from delegate.task import create_task, format_task_id
        from delegate.bootstrap import get_member_by_role
        from delegate.mailbox import read_inbox

        task = create_task(tmp_team, TEAM, title="Test task", assignee="alice")
        manager = get_member_by_role(tmp_team, TEAM, "manager")
        assert manager is not None

        # Simulate the updated merge success notification
        _notify_manager_sync(
            tmp_team, TEAM,
            f"Task {format_task_id(task['id'])} has been merged successfully. Check status of tasks and agents -- make any necessary assignment decisions.",
        )

        messages = read_inbox(tmp_team, TEAM, manager)
        # Should have "merged successfully" once, not twice
        found = any(
            "merged successfully" in m.body and "Check status of tasks and agents" in m.body
            for m in messages
        )
        assert found, f"Expected merge success with check prompt, got: {messages}"

        # Verify it doesn't contain redundant "Merged successfully" at the end
        redundant = any("merged successfully. Merged successfully" in m.body for m in messages)
        assert not redundant, "Merge notification should not duplicate 'merged successfully'"

    def test_merge_failure_includes_error_message(self, tmp_team):
        """Merge failure notification includes the error details."""
        from delegate.task import create_task, format_task_id
        from delegate.bootstrap import get_member_by_role
        from delegate.mailbox import read_inbox

        task = create_task(tmp_team, TEAM, title="Test task", assignee="alice")
        manager = get_member_by_role(tmp_team, TEAM, "manager")
        assert manager is not None

        # Simulate merge failure notification with error message
        error_message = "Merge conflict in file.py line 42"
        _notify_manager_sync(
            tmp_team, TEAM,
            f"Task {format_task_id(task['id'])} merge failed: {error_message}",
        )

        messages = read_inbox(tmp_team, TEAM, manager)
        found = any(
            "merge failed" in m.body and error_message in m.body
            for m in messages
        )
        assert found, f"Expected merge failure with error message, got: {messages}"


class TestStartupNotification:
    def test_startup_sends_summary(self, tmp_team):
        """Daemon startup notification includes task counts."""
        from delegate.task import create_task
        from delegate.bootstrap import get_member_by_role
        from delegate.mailbox import read_inbox

        # Create some tasks
        create_task(tmp_team, TEAM, title="Task 1", assignee="alice")
        create_task(tmp_team, TEAM, title="Task 2", assignee="bob")

        manager = get_member_by_role(tmp_team, TEAM, "manager")
        assert manager is not None

        # Simulate the startup notification
        from delegate.task import list_tasks
        all_tasks = list_tasks(tmp_team, TEAM)
        active = [t for t in all_tasks if t.get("status") not in ("done", "cancelled")]
        summary = (
            f"Daemon started. Team '{TEAM}' has {len(all_tasks)} total tasks "
            f"({len(active)} active)."
        )
        _notify_manager_sync(tmp_team, TEAM, summary)

        messages = read_inbox(tmp_team, TEAM, manager)
        found = any("Daemon started" in m.body and "2 total tasks" in m.body for m in messages)
        assert found, f"Expected startup summary in manager inbox, got: {messages}"

    def test_startup_includes_check_status_prompt(self, tmp_team):
        """Startup notification includes prompt to check status and wake agents."""
        from delegate.task import create_task, list_tasks
        from delegate.bootstrap import get_member_by_role
        from delegate.mailbox import read_inbox

        # Create a task
        create_task(tmp_team, TEAM, title="Task 1", assignee="alice")

        manager = get_member_by_role(tmp_team, TEAM, "manager")
        assert manager is not None

        # Simulate the updated startup notification
        all_tasks = list_tasks(tmp_team, TEAM)
        active = [t for t in all_tasks if t.get("status") not in ("done", "cancelled")]
        summary = (
            f"Daemon started. Team '{TEAM}' has {len(all_tasks)} total tasks "
            f"({len(active)} active).\n"
            f"Check status of all tasks and agents -- assign/reassign as needed and send messages to wake up relevant agents."
        )
        _notify_manager_sync(tmp_team, TEAM, summary)

        messages = read_inbox(tmp_team, TEAM, manager)
        found = any(
            "Check status of all tasks and agents" in m.body and "wake up relevant agents" in m.body
            for m in messages
        )
        assert found, f"Expected check status prompt in startup notification, got: {messages}"

    def test_startup_fallback_includes_check_status_prompt(self, tmp_team):
        """Fallback startup notification includes prompt to check status."""
        from delegate.bootstrap import get_member_by_role
        from delegate.mailbox import read_inbox

        manager = get_member_by_role(tmp_team, TEAM, "manager")
        assert manager is not None

        # Simulate the fallback startup notification (when task list fails)
        summary = f"Daemon started for team '{TEAM}'. Check status of all tasks and agents -- assign/reassign as needed and send messages to wake up relevant agents."
        _notify_manager_sync(tmp_team, TEAM, summary)

        messages = read_inbox(tmp_team, TEAM, manager)
        found = any(
            "Daemon started for team" in m.body and "Check status of all tasks and agents" in m.body
            for m in messages
        )
        assert found, f"Expected check status prompt in fallback startup notification, got: {messages}"
