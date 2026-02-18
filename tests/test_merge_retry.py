"""Tests for WORKTREE_ERROR exponential backoff retry logic.

Verifies:
- _worktree_retry_delay() returns values in the expected range with jitter.
- WORKTREE_ERROR is retryable (not escalated on first failure).
- retry_after is set on WORKTREE_ERROR and respected by merge_once (skip logic).
- On max attempts exhausted, WORKTREE_ERROR escalates to merge_failed.
- retry_after is cleared before the next merge attempt.
- Other retryable failures (DIRTY_MAIN etc.) are unaffected by the backoff logic.
"""

import time
from unittest.mock import patch, MagicMock

import pytest

from delegate.bootstrap import bootstrap
from delegate.config import add_repo, set_boss
from delegate.merge import (
    MergeFailureReason,
    MergeResult,
    _handle_merge_failure,
    _worktree_retry_delay,
    merge_once,
    MAX_MERGE_ATTEMPTS,
    _WORKTREE_RETRY_BASE,
    _WORKTREE_RETRY_JITTER,
)
from delegate.task import (
    create_task,
    change_status,
    get_task,
    update_task,
)


SAMPLE_TEAM = "myteam"


@pytest.fixture
def hc_home(tmp_path):
    """Create a bootstrapped delegate home directory."""
    hc = tmp_path / "hc_home"
    hc.mkdir()
    set_boss(hc, "nikhil")
    bootstrap(hc, SAMPLE_TEAM, manager="delegate", agents=["porter"])
    return hc


def _make_merging_task(hc_home, title="Task", repo="myrepo", branch="feature/test"):
    """Create a task in merging status."""
    task = create_task(hc_home, SAMPLE_TEAM, title=title, assignee="porter")
    update_task(hc_home, SAMPLE_TEAM, task["id"], repo=repo, branch=branch)
    change_status(hc_home, SAMPLE_TEAM, task["id"], "in_progress")
    change_status(hc_home, SAMPLE_TEAM, task["id"], "in_review")
    change_status(hc_home, SAMPLE_TEAM, task["id"], "in_approval")
    change_status(hc_home, SAMPLE_TEAM, task["id"], "merging")
    return get_task(hc_home, SAMPLE_TEAM, task["id"])


# ---------------------------------------------------------------------------
# _worktree_retry_delay
# ---------------------------------------------------------------------------


class TestWorktreeRetryDelay:
    def test_attempt_1_near_5s(self):
        """First retry delay is approximately 5 seconds."""
        delay = _worktree_retry_delay(1)
        # base=5, jitter=+-30% = [3.5, 6.5], but floor is 5.0
        assert 5.0 <= delay <= _WORKTREE_RETRY_BASE * (1 + _WORKTREE_RETRY_JITTER)

    def test_attempt_2_near_15s(self):
        """Second retry delay is approximately 15 seconds."""
        for _ in range(20):
            delay = _worktree_retry_delay(2)
            base = _WORKTREE_RETRY_BASE * 3  # 15
            low = base * (1 - _WORKTREE_RETRY_JITTER)
            high = base * (1 + _WORKTREE_RETRY_JITTER)
            assert low <= delay <= high, f"delay {delay} out of range [{low}, {high}]"

    def test_attempt_3_near_45s(self):
        """Third retry delay is approximately 45 seconds."""
        for _ in range(20):
            delay = _worktree_retry_delay(3)
            base = _WORKTREE_RETRY_BASE * 9  # 45
            low = base * (1 - _WORKTREE_RETRY_JITTER)
            high = base * (1 + _WORKTREE_RETRY_JITTER)
            assert low <= delay <= high, f"delay {delay} out of range [{low}, {high}]"

    def test_minimum_floor_is_5s(self):
        """Delay never goes below 5 seconds regardless of jitter."""
        # Monkey-patch random to always return minimum
        with patch("delegate.merge.random.random", return_value=0.0):
            delay = _worktree_retry_delay(1)
        assert delay >= 5.0

    def test_delays_grow_exponentially(self):
        """Delays for consecutive attempts increase exponentially."""
        # Use deterministic random (midpoint = no jitter)
        with patch("delegate.merge.random.random", return_value=0.5):
            d1 = _worktree_retry_delay(1)
            d2 = _worktree_retry_delay(2)
            d3 = _worktree_retry_delay(3)
        assert d1 < d2 < d3
        # Each step ~3x the previous
        assert 2.5 <= d2 / d1 <= 3.5
        assert 2.5 <= d3 / d2 <= 3.5


# ---------------------------------------------------------------------------
# WORKTREE_ERROR retryability
# ---------------------------------------------------------------------------


class TestWorktreeErrorRetryable:
    def test_worktree_error_is_retryable(self):
        """WORKTREE_ERROR.retryable must be True after the fix."""
        assert MergeFailureReason.WORKTREE_ERROR.retryable is True

    def test_non_retryable_reasons_unchanged(self):
        """REBASE_CONFLICT and PRE_MERGE_FAILED remain non-retryable."""
        assert MergeFailureReason.REBASE_CONFLICT.retryable is False
        assert MergeFailureReason.PRE_MERGE_FAILED.retryable is False
        assert MergeFailureReason.SQUASH_CONFLICT.retryable is False


# ---------------------------------------------------------------------------
# _handle_merge_failure — retry_after scheduling
# ---------------------------------------------------------------------------


class TestHandleMergeFailureWorktreeError:
    def _worktree_result(self, task_id):
        return MergeResult(
            task_id, False,
            "Could not acquire worktree lock",
            reason=MergeFailureReason.WORKTREE_ERROR,
        )

    def test_first_worktree_error_sets_retry_after(self, hc_home):
        """First WORKTREE_ERROR sets retry_after in the future."""
        task = _make_merging_task(hc_home)
        task_id = task["id"]

        before = time.time()
        _handle_merge_failure(hc_home, SAMPLE_TEAM, task_id, self._worktree_result(task_id))
        after = time.time()

        updated = get_task(hc_home, SAMPLE_TEAM, task_id)
        assert updated["status"] == "merging", "Should stay in merging on first failure"
        retry_after = updated.get("retry_after")
        assert retry_after is not None, "retry_after should be set"
        # Should be between 5s and ~6.5s in the future (attempt 1)
        assert before + 5.0 <= retry_after <= after + _WORKTREE_RETRY_BASE * (1 + _WORKTREE_RETRY_JITTER) + 1

    def test_first_worktree_error_increments_merge_attempts(self, hc_home):
        """First WORKTREE_ERROR increments merge_attempts to 1."""
        task = _make_merging_task(hc_home)
        task_id = task["id"]

        _handle_merge_failure(hc_home, SAMPLE_TEAM, task_id, self._worktree_result(task_id))

        updated = get_task(hc_home, SAMPLE_TEAM, task_id)
        assert updated.get("merge_attempts") == 1

    def test_second_worktree_error_sets_longer_retry(self, hc_home):
        """Second WORKTREE_ERROR sets a longer retry_after (~15s)."""
        task = _make_merging_task(hc_home)
        task_id = task["id"]

        # First failure
        _handle_merge_failure(hc_home, SAMPLE_TEAM, task_id, self._worktree_result(task_id))
        # Second failure
        before = time.time()
        _handle_merge_failure(hc_home, SAMPLE_TEAM, task_id, self._worktree_result(task_id))
        after = time.time()

        updated = get_task(hc_home, SAMPLE_TEAM, task_id)
        assert updated["status"] == "merging"
        assert updated.get("merge_attempts") == 2
        retry_after = updated.get("retry_after")
        assert retry_after is not None
        base2 = _WORKTREE_RETRY_BASE * 3  # 15s
        assert before + base2 * (1 - _WORKTREE_RETRY_JITTER) <= retry_after <= after + base2 * (1 + _WORKTREE_RETRY_JITTER) + 1

    def test_third_worktree_error_escalates(self, hc_home):
        """Third WORKTREE_ERROR (max attempts) escalates to merge_failed."""
        task = _make_merging_task(hc_home)
        task_id = task["id"]

        # Simulate 2 prior attempts
        update_task(hc_home, SAMPLE_TEAM, task_id, merge_attempts=MAX_MERGE_ATTEMPTS - 1)

        _handle_merge_failure(hc_home, SAMPLE_TEAM, task_id, self._worktree_result(task_id))

        updated = get_task(hc_home, SAMPLE_TEAM, task_id)
        assert updated["status"] == "merge_failed", "Should escalate after max attempts"

    def test_dirty_main_does_not_set_retry_after(self, hc_home):
        """DIRTY_MAIN (other retryable) does NOT set retry_after."""
        task = _make_merging_task(hc_home)
        task_id = task["id"]

        result = MergeResult(
            task_id, False,
            "Main has uncommitted changes",
            reason=MergeFailureReason.DIRTY_MAIN,
        )
        _handle_merge_failure(hc_home, SAMPLE_TEAM, task_id, result)

        updated = get_task(hc_home, SAMPLE_TEAM, task_id)
        assert updated["status"] == "merging"
        # retry_after should not be set for DIRTY_MAIN
        assert updated.get("retry_after") is None


# ---------------------------------------------------------------------------
# merge_once skip logic
# ---------------------------------------------------------------------------


class TestMergeOnceSkipRetryAfter:
    def _fail_with_worktree_error(self, task_id):
        return MergeResult(
            task_id, False,
            "Could not acquire worktree lock",
            reason=MergeFailureReason.WORKTREE_ERROR,
        )

    def test_skips_task_when_retry_after_in_future(self, hc_home):
        """merge_once skips a merging task whose retry_after is in the future."""
        task = _make_merging_task(hc_home)
        task_id = task["id"]

        # Set retry_after 60s in the future
        update_task(hc_home, SAMPLE_TEAM, task_id, retry_after=time.time() + 60)

        with patch("delegate.merge.merge_task") as mock_merge:
            merge_once(hc_home, SAMPLE_TEAM)
            mock_merge.assert_not_called()

    def test_processes_task_when_retry_after_elapsed(self, hc_home, tmp_path):
        """merge_once processes a merging task whose retry_after has passed."""
        task = _make_merging_task(hc_home)
        task_id = task["id"]

        # Set retry_after in the past
        update_task(hc_home, SAMPLE_TEAM, task_id, retry_after=time.time() - 1)

        success_result = MergeResult(task_id, True, "Merged successfully")
        with patch("delegate.merge.merge_task", return_value=success_result) as mock_merge:
            merge_once(hc_home, SAMPLE_TEAM)
            mock_merge.assert_called_once()

    def test_clears_retry_after_before_attempt(self, hc_home):
        """merge_once clears retry_after before processing (so a later check won't skip)."""
        task = _make_merging_task(hc_home)
        task_id = task["id"]

        # Set retry_after in the past (ready to retry)
        update_task(hc_home, SAMPLE_TEAM, task_id, retry_after=time.time() - 1)

        success_result = MergeResult(task_id, True, "Merged successfully")
        with patch("delegate.merge.merge_task", return_value=success_result):
            merge_once(hc_home, SAMPLE_TEAM)

        # After a successful merge, task is 'done' — retry_after is cleared
        updated = get_task(hc_home, SAMPLE_TEAM, task_id)
# Status is 'done' (merge_task mock returned success)
        # retry_after should have been cleared before the call
        assert updated.get("retry_after") is None

    def test_tasks_without_retry_after_are_processed(self, hc_home):
        """Tasks in merging without retry_after are always processed."""
        task = _make_merging_task(hc_home)
        task_id = task["id"]

        # Ensure no retry_after
        assert get_task(hc_home, SAMPLE_TEAM, task_id).get("retry_after") is None

        success_result = MergeResult(task_id, True, "Merged successfully")
        with patch("delegate.merge.merge_task", return_value=success_result) as mock_merge:
            merge_once(hc_home, SAMPLE_TEAM)
            mock_merge.assert_called_once()
