"""Tests for the review module — per-attempt verdicts and inline comments."""

import pytest
from pathlib import Path
from delegate.db import get_connection
from delegate.review import (
    create_review,
    get_reviews,
    get_current_review,
    set_verdict,
    add_comment,
    get_comments,
)
from delegate.task import create_task, change_status, get_task


@pytest.fixture()
def team_home(tmp_path):
    """Set up a minimal team home with DB and an in_approval task."""
    hc_home = tmp_path / "home"
    team = "acme"
    team_dir = hc_home / "teams" / team
    team_dir.mkdir(parents=True)

    # Create the DB (triggers schema + migrations)
    conn = get_connection(hc_home, team)
    conn.close()

    return hc_home, team


@pytest.fixture()
def task_in_approval(team_home):
    """Create a task and move it to in_approval so review_attempt is incremented."""
    hc_home, team = team_home
    task = create_task(hc_home, team, title="Fix widgets", assignee="alice", priority="high", repo=[])
    tid = task["id"]

    # Move through valid transitions: todo -> in_progress -> in_review -> in_approval
    change_status(hc_home, team, tid, "in_progress")
    change_status(hc_home, team, tid, "in_review")
    change_status(hc_home, team, tid, "in_approval")

    task = get_task(hc_home, team, tid)
    return hc_home, team, task


class TestReviewCreation:
    """Tests for creating and retrieving reviews."""

    def test_create_review(self, team_home):
        hc_home, team = team_home
        review = create_review(hc_home, team, task_id=1, attempt=1, reviewer="boss")
        assert review["task_id"] == 1
        assert review["attempt"] == 1
        assert review["verdict"] is None
        assert review["reviewer"] == "boss"
        assert review["decided_at"] is None

    def test_review_created_on_in_approval(self, task_in_approval):
        """When change_status moves a task to in_approval, a review row is auto-created."""
        hc_home, team, task = task_in_approval
        assert task["review_attempt"] == 1

        reviews = get_reviews(hc_home, team, task["id"])
        assert len(reviews) == 1
        assert reviews[0]["attempt"] == 1
        assert reviews[0]["verdict"] is None

    def test_get_current_review(self, task_in_approval):
        hc_home, team, task = task_in_approval
        current = get_current_review(hc_home, team, task["id"])
        assert current is not None
        assert current["attempt"] == 1
        assert current["verdict"] is None

    def test_get_current_review_nonexistent(self, team_home):
        hc_home, team = team_home
        current = get_current_review(hc_home, team, 9999)
        assert current is None


class TestReviewVerdicts:
    """Tests for setting verdicts."""

    def test_set_approved(self, task_in_approval):
        hc_home, team, task = task_in_approval
        result = set_verdict(hc_home, team, task["id"], 1, "approved", summary="LGTM", reviewer="boss")
        assert result["verdict"] == "approved"
        assert result["summary"] == "LGTM"
        assert result["decided_at"] is not None

    def test_set_rejected(self, task_in_approval):
        hc_home, team, task = task_in_approval
        result = set_verdict(hc_home, team, task["id"], 1, "rejected", summary="Needs work", reviewer="boss")
        assert result["verdict"] == "rejected"
        assert result["summary"] == "Needs work"

    def test_invalid_verdict(self, task_in_approval):
        hc_home, team, task = task_in_approval
        with pytest.raises(ValueError, match="Invalid verdict"):
            set_verdict(hc_home, team, task["id"], 1, "maybe")


class TestReviewComments:
    """Tests for inline review comments."""

    def test_add_comment_with_line(self, task_in_approval):
        hc_home, team, task = task_in_approval
        comment = add_comment(
            hc_home, team, task["id"], 1,
            file="src/widget.py", body="This shouldn't be mutable", author="boss",
            line=42,
        )
        assert comment["file"] == "src/widget.py"
        assert comment["line"] == 42
        assert comment["body"] == "This shouldn't be mutable"
        assert comment["author"] == "boss"
        assert comment["attempt"] == 1

    def test_add_comment_without_line(self, task_in_approval):
        hc_home, team, task = task_in_approval
        comment = add_comment(
            hc_home, team, task["id"], 1,
            file="README.md", body="Needs more docs", author="boss",
        )
        assert comment["file"] == "README.md"
        assert comment["line"] is None

    def test_get_comments_by_attempt(self, task_in_approval):
        hc_home, team, task = task_in_approval
        add_comment(hc_home, team, task["id"], 1, file="a.py", body="fix", author="boss")
        add_comment(hc_home, team, task["id"], 1, file="b.py", body="also fix", author="boss")

        comments = get_comments(hc_home, team, task["id"], attempt=1)
        assert len(comments) == 2

    def test_get_comments_all_attempts(self, team_home):
        hc_home, team = team_home
        # Manually create two review attempts
        create_review(hc_home, team, task_id=1, attempt=1)
        create_review(hc_home, team, task_id=1, attempt=2)
        add_comment(hc_home, team, 1, 1, file="a.py", body="old comment", author="boss")
        add_comment(hc_home, team, 1, 2, file="a.py", body="new comment", author="boss")

        all_comments = get_comments(hc_home, team, 1)
        assert len(all_comments) == 2

    def test_current_review_includes_comments(self, task_in_approval):
        hc_home, team, task = task_in_approval
        add_comment(hc_home, team, task["id"], 1, file="x.py", body="fix this", author="boss", line=10)

        current = get_current_review(hc_home, team, task["id"])
        assert current is not None
        assert len(current["comments"]) == 1
        assert current["comments"][0]["file"] == "x.py"


class TestMultipleAttempts:
    """Tests for multiple review cycles."""

    def test_second_attempt_fresh_verdict(self, task_in_approval):
        """After rejection and re-submission, a fresh review is created."""
        hc_home, team, task = task_in_approval

        # Reject attempt 1
        set_verdict(hc_home, team, task["id"], 1, "rejected", summary="Needs work")
        change_status(hc_home, team, task["id"], "rejected")

        # Rework: back to in_progress, then through review, then in_approval
        change_status(hc_home, team, task["id"], "in_progress")
        change_status(hc_home, team, task["id"], "in_review")
        change_status(hc_home, team, task["id"], "in_approval")

        task = get_task(hc_home, team, task["id"])
        assert task["review_attempt"] == 2

        # Should have 2 reviews
        reviews = get_reviews(hc_home, team, task["id"])
        assert len(reviews) == 2

        # Current review is fresh (no verdict)
        current = get_current_review(hc_home, team, task["id"])
        assert current["attempt"] == 2
        assert current["verdict"] is None

    def test_old_comments_preserved(self, task_in_approval):
        """Comments from attempt 1 are preserved after starting attempt 2."""
        hc_home, team, task = task_in_approval

        add_comment(hc_home, team, task["id"], 1, file="old.py", body="old issue", author="boss")
        set_verdict(hc_home, team, task["id"], 1, "rejected")

        change_status(hc_home, team, task["id"], "rejected")
        change_status(hc_home, team, task["id"], "in_progress")
        change_status(hc_home, team, task["id"], "in_review")
        change_status(hc_home, team, task["id"], "in_approval")

        # All comments across attempts
        all_comments = get_comments(hc_home, team, task["id"])
        assert len(all_comments) == 1
        assert all_comments[0]["attempt"] == 1
        assert all_comments[0]["body"] == "old issue"

        # Comments for attempt 2 only
        new_comments = get_comments(hc_home, team, task["id"], attempt=2)
        assert len(new_comments) == 0
