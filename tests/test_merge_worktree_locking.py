"""Tests for merge flow rework: agent worktree reset, locking, and state gate.

Covers the behaviors introduced in T0071:
1. Agent worktree is reset to rebased tip after successful rebase.
2. base_sha is updated to current main HEAD after the reset.
3. Task state gate: agents with merging-state tasks are identified correctly.
4. TelephoneExchange worktree lock API works correctly.
5. Pre-merge tests run in agent worktree (not disposable WT).
6. _ff_merge_to_sha works correctly.
"""

import asyncio
import subprocess
from pathlib import Path

import pytest

from delegate.task import (
    create_task,
    change_status,
    update_task,
    get_task,
)
from delegate.config import add_repo, set_boss, set_pre_merge_script
from delegate.merge import (
    merge_task,
    _reset_agent_worktree,
    _ff_merge_to_sha,
    MergeFailureReason,
)
from delegate.runtime import TelephoneExchange, AsyncRWLock
from delegate.bootstrap import bootstrap
from delegate.paths import task_worktree_dir


SAMPLE_TEAM = "myteam"


@pytest.fixture
def hc_home(tmp_path):
    hc = tmp_path / "hc_home"
    hc.mkdir()
    set_boss(hc, "nikhil")
    bootstrap(hc, SAMPLE_TEAM, manager="edison", agents=["alice", "bob"])
    return hc


def _setup_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True)
    (repo / "README.md").write_text("# Test repo\n")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo), capture_output=True)
    return repo


def _make_feature_branch(repo: Path, branch: str, filename: str = "feature.py"):
    subprocess.run(["git", "checkout", "-b", branch], cwd=str(repo), capture_output=True, check=True)
    (repo / filename).write_text("# Feature\n")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", f"Add {filename}"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "checkout", "main"], cwd=str(repo), capture_output=True, check=True)


def _register_repo(hc_home: Path, name: str, source_repo: Path):
    from delegate.paths import repos_dir
    rd = repos_dir(hc_home, SAMPLE_TEAM)
    rd.mkdir(parents=True, exist_ok=True)
    link = rd / name
    if not link.exists():
        link.symlink_to(source_repo)
    add_repo(hc_home, SAMPLE_TEAM, name, str(source_repo), approval="auto")


def _make_merging_task(hc_home, repo="myrepo", branch="feature/test"):
    task = create_task(hc_home, SAMPLE_TEAM, title="Task", assignee="alice")
    update_task(hc_home, SAMPLE_TEAM, task["id"], repo=repo, branch=branch)
    change_status(hc_home, SAMPLE_TEAM, task["id"], "in_progress")
    change_status(hc_home, SAMPLE_TEAM, task["id"], "in_review")
    change_status(hc_home, SAMPLE_TEAM, task["id"], "in_approval")
    change_status(hc_home, SAMPLE_TEAM, task["id"], "merging")
    return get_task(hc_home, SAMPLE_TEAM, task["id"])


def _create_agent_worktree(hc_home: Path, repo: Path, repo_name: str, branch: str, task_id: int) -> Path:
    wt_path = task_worktree_dir(hc_home, SAMPLE_TEAM, repo_name, task_id)
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "worktree", "add", str(wt_path), branch],
        cwd=str(repo), capture_output=True, check=True,
    )
    return wt_path


# ---------------------------------------------------------------------------
# Tests: agent worktree reset
# ---------------------------------------------------------------------------

class TestAgentWorktreeReset:
    def test_merge_succeeds_with_agent_worktree(self, hc_home, tmp_path):
        """merge_task succeeds when agent worktree exists and is reset to rebased tip."""
        repo = _setup_git_repo(tmp_path)
        branch = "feature/test"
        _make_feature_branch(repo, branch)
        _register_repo(hc_home, "myrepo", repo)

        task = _make_merging_task(hc_home, repo="myrepo", branch=branch)
        _create_agent_worktree(hc_home, repo, "myrepo", branch, task["id"])

        result = merge_task(hc_home, SAMPLE_TEAM, task["id"], skip_tests=True)
        assert result.success is True

        updated = get_task(hc_home, SAMPLE_TEAM, task["id"])
        assert updated["status"] == "done"
        # merge_tip proves FF-merge completed
        assert updated.get("merge_tip", {}).get("myrepo", "") != ""

    def test_base_sha_updated_after_reset(self, hc_home, tmp_path):
        """base_sha is updated to current main HEAD after the agent WT reset."""
        repo = _setup_git_repo(tmp_path)
        branch = "feature/test"
        _make_feature_branch(repo, branch)
        _register_repo(hc_home, "myrepo", repo)

        main_head = subprocess.run(
            ["git", "rev-parse", "main"], cwd=str(repo), capture_output=True, text=True
        ).stdout.strip()

        task = _make_merging_task(hc_home, repo="myrepo", branch=branch)
        _create_agent_worktree(hc_home, repo, "myrepo", branch, task["id"])

        result = merge_task(hc_home, SAMPLE_TEAM, task["id"], skip_tests=True)
        assert result.success is True

        # base_sha was updated to main HEAD (the rebase point)
        updated = get_task(hc_home, SAMPLE_TEAM, task["id"])
        assert updated.get("base_sha", {}).get("myrepo", "") == main_head

    def test_reset_skipped_when_no_agent_worktree(self, hc_home, tmp_path):
        """When agent worktree doesn't exist, reset is skipped and merge succeeds."""
        repo = _setup_git_repo(tmp_path)
        branch = "feature/test"
        _make_feature_branch(repo, branch)
        _register_repo(hc_home, "myrepo", repo)

        task = _make_merging_task(hc_home, repo="myrepo", branch=branch)
        # No agent worktree created

        result = merge_task(hc_home, SAMPLE_TEAM, task["id"], skip_tests=True)
        assert result.success is True

    def test_untracked_files_preserved_after_reset(self, hc_home, tmp_path):
        """git reset --hard preserves untracked files in the agent worktree."""
        repo = _setup_git_repo(tmp_path)
        branch = "feature/env"
        _make_feature_branch(repo, branch)
        _register_repo(hc_home, "myrepo", repo)

        task = _make_merging_task(hc_home, repo="myrepo", branch=branch)
        agent_wt = _create_agent_worktree(hc_home, repo, "myrepo", branch, task["id"])

        # Create an untracked "environment" file in the agent WT
        untracked = agent_wt / ".env_artifact"
        untracked.write_text("build cache\n")

        # Get tip (reset to same tip is a no-op change but exercises the path)
        tip = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(agent_wt), capture_output=True, text=True
        ).stdout.strip()

        ok, msg = _reset_agent_worktree(hc_home, SAMPLE_TEAM, task["id"], "myrepo", str(repo), tip)
        assert ok is True

        # Untracked file is still there
        assert untracked.exists()
        assert untracked.read_text() == "build cache\n"


# ---------------------------------------------------------------------------
# Tests: _ff_merge_to_sha
# ---------------------------------------------------------------------------

class TestFfMergeToSha:
    def _setup_repo_with_feature(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=str(repo), capture_output=True)
        (repo / "a.txt").write_text("a\n")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=str(repo), capture_output=True)
        (repo / "b.txt").write_text("b\n")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "add b"], cwd=str(repo), capture_output=True)
        tip = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
        ).stdout.strip()
        subprocess.run(["git", "checkout", "main"], cwd=str(repo), capture_output=True)
        return repo, tip

    def test_ff_merge_to_sha_succeeds(self, tmp_path):
        """_ff_merge_to_sha fast-forwards main to a valid descendant SHA."""
        repo, tip = self._setup_repo_with_feature(tmp_path)
        ok, msg = _ff_merge_to_sha(str(repo), tip)
        assert ok is True
        new_main = subprocess.run(
            ["git", "rev-parse", "main"], cwd=str(repo), capture_output=True, text=True
        ).stdout.strip()
        assert new_main == tip

    def test_ff_merge_to_sha_fails_non_ancestor(self, tmp_path):
        """_ff_merge_to_sha fails when SHA is not a descendant of main."""
        repo, tip = self._setup_repo_with_feature(tmp_path)
        # Advance main so feature is no longer a descendant
        (repo / "c.txt").write_text("c\n")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "advance main"], cwd=str(repo), capture_output=True)

        ok, msg = _ff_merge_to_sha(str(repo), tip)
        assert ok is False
        assert "not possible" in msg.lower() or "not a descendant" in msg.lower()


# ---------------------------------------------------------------------------
# Tests: TelephoneExchange worktree locks
# ---------------------------------------------------------------------------

class TestWorktreeLocks:
    def test_lock_created_on_demand(self):
        exchange = TelephoneExchange()
        lock = exchange.worktree_lock("myteam", 42)
        assert lock is not None
        assert isinstance(lock, AsyncRWLock)

    def test_same_lock_returned(self):
        exchange = TelephoneExchange()
        lock1 = exchange.worktree_lock("myteam", 42)
        lock2 = exchange.worktree_lock("myteam", 42)
        assert lock1 is lock2

    def test_different_task_ids_get_different_locks(self):
        exchange = TelephoneExchange()
        assert exchange.worktree_lock("myteam", 1) is not exchange.worktree_lock("myteam", 2)

    def test_different_teams_get_different_locks(self):
        exchange = TelephoneExchange()
        assert exchange.worktree_lock("team_a", 1) is not exchange.worktree_lock("team_b", 1)

    def test_discard_removes_lock(self):
        exchange = TelephoneExchange()
        lock1 = exchange.worktree_lock("myteam", 5)
        exchange.discard_worktree_lock("myteam", 5)
        lock2 = exchange.worktree_lock("myteam", 5)
        assert lock1 is not lock2

    def test_discard_nonexistent_lock_is_safe(self):
        exchange = TelephoneExchange()
        exchange.discard_worktree_lock("myteam", 999)  # Must not raise

    def test_rwlock_multiple_readers(self):
        """Multiple readers can hold the lock simultaneously without blocking."""
        async def _run():
            lock = AsyncRWLock()
            await lock.acquire_read()
            await lock.acquire_read()  # Second reader should not block
            assert lock._readers == 2
            await lock.release_read()
            await lock.release_read()
            assert lock._readers == 0

        asyncio.run(_run())

    def test_rwlock_writer_excludes_readers(self):
        """Writer blocks new readers from acquiring until write lock is released."""
        async def _run():
            lock = AsyncRWLock()
            await lock.acquire_write()
            assert lock._writer is True

            # Try to acquire read -- should not complete while writer holds
            read_acquired = False

            async def _reader():
                nonlocal read_acquired
                await lock.acquire_read()
                read_acquired = True
                await lock.release_read()

            task = asyncio.ensure_future(_reader())
            # Yield control so _reader gets a chance to run
            await asyncio.sleep(0)
            # Reader should still be blocked
            assert read_acquired is False

            await lock.release_write()
            # Now reader should complete
            await asyncio.wait_for(task, timeout=1.0)
            assert read_acquired is True

        asyncio.run(_run())

    def test_rwlock_writer_waits_for_readers(self):
        """Writer waits until all active readers release before acquiring."""
        async def _run():
            lock = AsyncRWLock()
            await lock.acquire_read()  # Reader holds lock

            write_acquired = False

            async def _writer():
                nonlocal write_acquired
                await lock.acquire_write()
                write_acquired = True
                await lock.release_write()

            task = asyncio.ensure_future(_writer())
            # Yield -- writer should be waiting
            await asyncio.sleep(0)
            assert write_acquired is False

            await lock.release_read()  # Release reader
            await asyncio.wait_for(task, timeout=1.0)
            assert write_acquired is True

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Tests: task state gate (dispatch logic)
# ---------------------------------------------------------------------------

class TestTaskStateGate:
    def test_merging_task_dri_would_be_blocked(self, hc_home):
        """Agent is the DRI of a merging task -> should be skipped for dispatch."""
        task = create_task(hc_home, SAMPLE_TEAM, title="A task", assignee="alice")
        update_task(hc_home, SAMPLE_TEAM, task["id"], repo="r", branch="b")
        change_status(hc_home, SAMPLE_TEAM, task["id"], "in_progress")
        change_status(hc_home, SAMPLE_TEAM, task["id"], "in_review")
        change_status(hc_home, SAMPLE_TEAM, task["id"], "in_approval")
        change_status(hc_home, SAMPLE_TEAM, task["id"], "merging")

        from delegate.task import list_tasks
        merging_tasks = list_tasks(hc_home, SAMPLE_TEAM, status="merging")
        agent_merging = any(t.get("dri") == "alice" for t in merging_tasks)
        assert agent_merging is True

    def test_non_dri_agent_not_blocked(self, hc_home):
        """Agent who isn't the DRI of a merging task is not blocked."""
        task = create_task(hc_home, SAMPLE_TEAM, title="A task", assignee="alice")
        update_task(hc_home, SAMPLE_TEAM, task["id"], repo="r", branch="b")
        change_status(hc_home, SAMPLE_TEAM, task["id"], "in_progress")
        change_status(hc_home, SAMPLE_TEAM, task["id"], "in_review")
        change_status(hc_home, SAMPLE_TEAM, task["id"], "in_approval")
        change_status(hc_home, SAMPLE_TEAM, task["id"], "merging")

        from delegate.task import list_tasks
        merging_tasks = list_tasks(hc_home, SAMPLE_TEAM, status="merging")
        agent_merging = any(t.get("dri") == "bob" for t in merging_tasks)
        assert agent_merging is False

    def test_no_merging_tasks_not_blocked(self, hc_home):
        from delegate.task import list_tasks
        merging_tasks = list_tasks(hc_home, SAMPLE_TEAM, status="merging")
        assert merging_tasks == []
        assert not any(t.get("dri") == "alice" for t in merging_tasks)

    def test_done_task_does_not_block(self, hc_home):
        """A done task does not block agent dispatch."""
        task = create_task(hc_home, SAMPLE_TEAM, title="A task", assignee="alice")
        update_task(hc_home, SAMPLE_TEAM, task["id"], repo="r", branch="b")
        for status in ["in_progress", "in_review", "in_approval", "merging", "done"]:
            change_status(hc_home, SAMPLE_TEAM, task["id"], status)

        from delegate.task import list_tasks
        merging_tasks = list_tasks(hc_home, SAMPLE_TEAM, status="merging")
        assert not any(t.get("dri") == "alice" for t in merging_tasks)
