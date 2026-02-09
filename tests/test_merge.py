"""Tests for scripts/merge.py — merge worker logic."""

from unittest.mock import patch, MagicMock, call
import subprocess

import pytest
import yaml

from scripts.task import (
    create_task,
    change_status,
    update_task,
    get_task,
)
from scripts.merge import (
    merge_once,
    _get_needs_merge_tasks,
    _do_merge,
    _notify_manager,
    _get_repo_approval,
    _get_repo_clone_path,
)


def _make_needs_merge_task(root, title="Task", repo="myrepo", branch="feature/test"):
    """Helper: create a task and advance it to needs_merge status."""
    task = create_task(root, title=title)
    update_task(root, task["id"], repo=repo, branch=branch)
    change_status(root, task["id"], "in_progress")
    change_status(root, task["id"], "review")
    change_status(root, task["id"], "needs_merge")
    return get_task(root, task["id"])


class TestGetNeedsMergeTasks:
    def test_empty_when_no_tasks(self, tmp_team):
        assert _get_needs_merge_tasks(tmp_team) == []

    def test_finds_needs_merge_tasks(self, tmp_team):
        _make_needs_merge_task(tmp_team, title="First")
        _make_needs_merge_task(tmp_team, title="Second")
        tasks = _get_needs_merge_tasks(tmp_team)
        assert len(tasks) == 2
        assert all(t["status"] == "needs_merge" for t in tasks)

    def test_excludes_other_statuses(self, tmp_team):
        create_task(tmp_team, title="Open task")
        task2 = create_task(tmp_team, title="In progress")
        change_status(tmp_team, task2["id"], "in_progress")
        _make_needs_merge_task(tmp_team, title="Merge me")

        tasks = _get_needs_merge_tasks(tmp_team)
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Merge me"

    def test_ordered_by_updated_at(self, tmp_team):
        t1 = _make_needs_merge_task(tmp_team, title="First")
        t2 = _make_needs_merge_task(tmp_team, title="Second")
        tasks = _get_needs_merge_tasks(tmp_team)
        assert tasks[0]["id"] == t1["id"]
        assert tasks[1]["id"] == t2["id"]


class TestDoMerge:
    def test_successful_merge(self, tmp_path):
        """Test _do_merge with a real git repo."""
        # Set up a bare "origin" repo
        origin = tmp_path / "origin.git"
        origin.mkdir()
        subprocess.run(["git", "init", "--bare", str(origin)], capture_output=True, check=True)

        # Clone it as our working repo
        clone = tmp_path / "clone"
        subprocess.run(["git", "clone", str(origin), str(clone)], capture_output=True, check=True)

        # Configure git user for commits
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(clone), capture_output=True)

        # Create initial commit on main
        (clone / "README.md").write_text("# Test repo\n")
        subprocess.run(["git", "add", "."], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=str(clone), capture_output=True)

        # Create a feature branch with changes
        subprocess.run(["git", "checkout", "-b", "feature/test"], cwd=str(clone), capture_output=True)
        (clone / "feature.py").write_text("# New feature\n")
        subprocess.run(["git", "add", "."], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add feature"], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "push", "origin", "feature/test"], cwd=str(clone), capture_output=True)

        # Go back to main
        subprocess.run(["git", "checkout", "main"], cwd=str(clone), capture_output=True)

        success, detail = _do_merge(clone, "feature/test")
        assert success is True
        assert "successful" in detail.lower()

        # Verify the feature file is now on main
        assert (clone / "feature.py").exists()

    def test_merge_conflict(self, tmp_path):
        """Test _do_merge detects conflicts and aborts cleanly."""
        origin = tmp_path / "origin.git"
        origin.mkdir()
        subprocess.run(["git", "init", "--bare", str(origin)], capture_output=True, check=True)

        clone = tmp_path / "clone"
        subprocess.run(["git", "clone", str(origin), str(clone)], capture_output=True, check=True)

        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(clone), capture_output=True)

        # Initial commit
        (clone / "file.txt").write_text("original content\n")
        subprocess.run(["git", "add", "."], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=str(clone), capture_output=True)

        # Feature branch changes the same file
        subprocess.run(["git", "checkout", "-b", "feature/conflict"], cwd=str(clone), capture_output=True)
        (clone / "file.txt").write_text("feature version\n")
        subprocess.run(["git", "add", "."], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Feature change"], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "push", "origin", "feature/conflict"], cwd=str(clone), capture_output=True)

        # Main also changes the same file
        subprocess.run(["git", "checkout", "main"], cwd=str(clone), capture_output=True)
        (clone / "file.txt").write_text("main version\n")
        subprocess.run(["git", "add", "."], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Main change"], cwd=str(clone), capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=str(clone), capture_output=True)

        success, detail = _do_merge(clone, "feature/conflict")
        assert success is False
        assert "conflict" in detail.lower() or "merge" in detail.lower()

        # Verify main is still clean (merge was aborted)
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(clone),
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "", "Working directory should be clean after merge abort"


class TestMergeOnce:
    def test_returns_zero_when_no_tasks(self, tmp_team):
        assert merge_once(tmp_team) == 0

    def test_skips_task_without_repo(self, tmp_team):
        """Tasks without a repo field should be skipped."""
        task = create_task(tmp_team, title="No repo")
        update_task(tmp_team, task["id"], branch="some/branch")
        change_status(tmp_team, task["id"], "in_progress")
        change_status(tmp_team, task["id"], "review")
        change_status(tmp_team, task["id"], "needs_merge")

        assert merge_once(tmp_team) == 0

    def test_skips_task_without_branch(self, tmp_team):
        """Tasks without a branch field should be skipped."""
        task = create_task(tmp_team, title="No branch")
        update_task(tmp_team, task["id"], repo="myrepo")
        change_status(tmp_team, task["id"], "in_progress")
        change_status(tmp_team, task["id"], "review")
        change_status(tmp_team, task["id"], "needs_merge")

        assert merge_once(tmp_team) == 0

    @patch("scripts.merge._get_repo_approval", return_value="manual")
    def test_skips_manual_unapproved(self, mock_approval, tmp_team):
        """Manual approval tasks without approval_status='approved' are skipped."""
        _make_needs_merge_task(tmp_team, title="Unapproved")
        assert merge_once(tmp_team) == 0

    @patch("scripts.merge._get_repo_approval", return_value="manual")
    @patch("scripts.merge._get_repo_clone_path")
    @patch("scripts.merge._do_merge", return_value=(True, "Merge successful"))
    def test_merges_manual_approved(self, mock_merge, mock_path, mock_approval, tmp_team, tmp_path):
        """Manual approval tasks with approval_status='approved' should be merged."""
        clone = tmp_path / "repos" / "myrepo"
        clone.mkdir(parents=True)
        mock_path.return_value = clone

        task = _make_needs_merge_task(tmp_team, title="Approved")
        update_task(tmp_team, task["id"], approval_status="approved")

        result = merge_once(tmp_team)
        assert result == 1
        assert mock_merge.called

        updated = get_task(tmp_team, task["id"])
        assert updated["status"] == "merged"
        assert updated["completed_at"] != ""

    @patch("scripts.merge._get_repo_approval", return_value="auto")
    @patch("scripts.merge._get_repo_clone_path")
    @patch("scripts.merge._do_merge", return_value=(True, "Merge successful"))
    def test_auto_merge(self, mock_merge, mock_path, mock_approval, tmp_team, tmp_path):
        """Auto approval tasks should merge without checking approval_status."""
        clone = tmp_path / "repos" / "myrepo"
        clone.mkdir(parents=True)
        mock_path.return_value = clone

        task = _make_needs_merge_task(tmp_team, title="Auto merge")

        result = merge_once(tmp_team)
        assert result == 1
        mock_merge.assert_called_once_with(clone, "feature/test")

        updated = get_task(tmp_team, task["id"])
        assert updated["status"] == "merged"

    @patch("scripts.merge._get_repo_approval", return_value="auto")
    @patch("scripts.merge._get_repo_clone_path")
    @patch("scripts.merge._do_merge", return_value=(False, "Merge conflict: CONFLICT in file.txt"))
    @patch("scripts.merge._notify_manager")
    def test_conflict_sets_status_and_notifies(
        self, mock_notify, mock_merge, mock_path, mock_approval, tmp_team, tmp_path
    ):
        """On merge conflict, status should become 'conflict' and manager notified."""
        clone = tmp_path / "repos" / "myrepo"
        clone.mkdir(parents=True)
        mock_path.return_value = clone

        task = _make_needs_merge_task(tmp_team, title="Conflict task")

        result = merge_once(tmp_team)
        assert result == 0  # conflict is not a successful merge

        updated = get_task(tmp_team, task["id"])
        assert updated["status"] == "conflict"

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert call_args[0][0] == tmp_team  # root
        assert call_args[0][1]["id"] == task["id"]  # task dict
        assert "conflict" in call_args[0][2].lower()  # detail

    @patch("scripts.merge._get_repo_approval", return_value="auto")
    @patch("scripts.merge._get_repo_clone_path")
    @patch("scripts.merge._do_merge", return_value=(True, "Merge successful"))
    def test_processes_only_one_per_cycle(self, mock_merge, mock_path, mock_approval, tmp_team, tmp_path):
        """merge_once should process at most one task per cycle."""
        clone = tmp_path / "repos" / "myrepo"
        clone.mkdir(parents=True)
        mock_path.return_value = clone

        _make_needs_merge_task(tmp_team, title="First", branch="branch/first")
        _make_needs_merge_task(tmp_team, title="Second", branch="branch/second")

        result = merge_once(tmp_team)
        assert result == 1
        assert mock_merge.call_count == 1

    @patch("scripts.merge._get_repo_approval", return_value="auto")
    @patch("scripts.merge._get_repo_clone_path")
    @patch("scripts.merge._do_merge", return_value=(True, "Merge successful"))
    def test_fifo_order(self, mock_merge, mock_path, mock_approval, tmp_team, tmp_path):
        """Oldest task (by updated_at) should be processed first."""
        clone = tmp_path / "repos" / "myrepo"
        clone.mkdir(parents=True)
        mock_path.return_value = clone

        t1 = _make_needs_merge_task(tmp_team, title="First", branch="branch/first")
        t2 = _make_needs_merge_task(tmp_team, title="Second", branch="branch/second")

        result = merge_once(tmp_team)
        assert result == 1

        # First task should have been merged
        updated_t1 = get_task(tmp_team, t1["id"])
        updated_t2 = get_task(tmp_team, t2["id"])
        assert updated_t1["status"] == "merged"
        assert updated_t2["status"] == "needs_merge"

    @patch("scripts.merge._get_repo_approval", return_value="auto")
    @patch("scripts.merge._get_repo_clone_path", return_value=None)
    def test_skips_missing_clone(self, mock_path, mock_approval, tmp_team):
        """Tasks whose repo clone doesn't exist should be skipped."""
        _make_needs_merge_task(tmp_team, title="No clone")
        assert merge_once(tmp_team) == 0


class TestNotifyManager:
    def test_sends_message_to_manager(self, tmp_team):
        """Notification should be sent to the team manager."""
        task = {
            "id": 1,
            "repo": "myrepo",
            "branch": "feature/test",
            "assignee": "alice",
        }

        with patch("scripts.merge.send_message") as mock_send:
            _notify_manager(tmp_team, task, "CONFLICT in file.txt")

            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert args[0] == tmp_team
            assert args[1] == "system"
            assert args[2] == "manager"  # the manager from conftest
            assert "T0001" in args[3]
            assert "CONFLICT" in args[3]
            assert "alice" in args[3]

    def test_handles_no_manager(self, tmp_team):
        """Should not crash if no manager is found."""
        task = {"id": 1, "repo": "r", "branch": "b", "assignee": "a"}

        with patch("scripts.merge.get_member_by_role", return_value=None):
            # Should not raise
            _notify_manager(tmp_team, task, "detail")


class TestGetRepoApproval:
    def test_returns_manual_by_default(self, tmp_team):
        """Without config, default should be 'manual'."""
        assert _get_repo_approval(tmp_team, "nonexistent") == "manual"

    def test_reads_from_config(self, tmp_team):
        """Should read approval setting from config.yaml."""
        # Create a config.yaml at the expected hc_home location
        hc_home = tmp_team.parent.parent.parent
        config_path = hc_home / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.dump({
            "repos": {
                "myrepo": {"source": "/tmp/repo", "approval": "auto"},
                "other": {"source": "/tmp/other", "approval": "manual"},
            }
        }))

        assert _get_repo_approval(tmp_team, "myrepo") == "auto"
        assert _get_repo_approval(tmp_team, "other") == "manual"
        assert _get_repo_approval(tmp_team, "missing") == "manual"
