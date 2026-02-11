"""Tests for delegate.review — per-attempt reviews and inline comments."""

import pytest
from fastapi.testclient import TestClient

from delegate.review import (
    create_review,
    get_reviews,
    get_current_review,
    set_verdict,
    add_comment,
    get_comments,
)
from delegate.task import create_task, change_status
from delegate.web import create_app

TEAM = "testteam"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_team):
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


@pytest.fixture
def task_id(tmp_team):
    """Create a task and move it to in_approval (which auto-creates review attempt 1)."""
    task = create_task(tmp_team, TEAM, title="Review target")
    change_status(tmp_team, TEAM, task["id"], "in_progress")
    change_status(tmp_team, TEAM, task["id"], "in_review")
    change_status(tmp_team, TEAM, task["id"], "in_approval")
    return task["id"]


# ---------------------------------------------------------------------------
# Unit tests — review CRUD
# ---------------------------------------------------------------------------

class TestCreateReview:
    def test_create_review_returns_dict(self, tmp_team, task_id):
        # Attempt 1 is auto-created; create attempt 2 manually
        review = create_review(tmp_team, TEAM, task_id, 2, reviewer="boss")
        assert review["task_id"] == task_id
        assert review["attempt"] == 2
        assert review["reviewer"] == "boss"
        assert review["verdict"] is None  # pending

    def test_create_review_duplicate_attempt_fails(self, tmp_team, task_id):
        # Attempt 1 already exists from the in_approval transition
        with pytest.raises(Exception):
            create_review(tmp_team, TEAM, task_id, 1, reviewer="boss")


class TestGetReviews:
    def test_get_reviews_returns_all(self, tmp_team, task_id):
        create_review(tmp_team, TEAM, task_id, 2, reviewer="boss")
        reviews = get_reviews(tmp_team, TEAM, task_id)
        assert len(reviews) >= 2
        assert reviews[0]["attempt"] == 1
        assert reviews[1]["attempt"] == 2

    def test_get_reviews_empty_for_nonexistent(self, tmp_team):
        reviews = get_reviews(tmp_team, TEAM, 9999)
        assert reviews == []


class TestGetCurrentReview:
    def test_returns_latest_attempt(self, tmp_team, task_id):
        review = get_current_review(tmp_team, TEAM, task_id)
        assert review is not None
        assert review["attempt"] == 1
        assert "comments" in review

    def test_returns_none_for_nonexistent(self, tmp_team):
        assert get_current_review(tmp_team, TEAM, 9999) is None

    def test_attaches_comments(self, tmp_team, task_id):
        add_comment(tmp_team, TEAM, task_id, 1, "main.py", "Fix this", "boss", line=42)
        review = get_current_review(tmp_team, TEAM, task_id)
        assert len(review["comments"]) == 1
        assert review["comments"][0]["body"] == "Fix this"


class TestSetVerdict:
    def test_set_approved(self, tmp_team, task_id):
        result = set_verdict(tmp_team, TEAM, task_id, 1, "approved", summary="LGTM", reviewer="boss")
        assert result["verdict"] == "approved"
        assert result["summary"] == "LGTM"
        assert result["decided_at"] is not None

    def test_set_rejected(self, tmp_team, task_id):
        result = set_verdict(tmp_team, TEAM, task_id, 1, "rejected", summary="Needs work")
        assert result["verdict"] == "rejected"
        assert result["summary"] == "Needs work"

    def test_invalid_verdict_raises(self, tmp_team, task_id):
        with pytest.raises(ValueError, match="Invalid verdict"):
            set_verdict(tmp_team, TEAM, task_id, 1, "maybe")

    def test_nonexistent_attempt_raises(self, tmp_team, task_id):
        with pytest.raises(ValueError, match="No review found"):
            set_verdict(tmp_team, TEAM, task_id, 99, "approved")


# ---------------------------------------------------------------------------
# Unit tests — comments CRUD
# ---------------------------------------------------------------------------

class TestAddComment:
    def test_returns_comment_dict(self, tmp_team, task_id):
        c = add_comment(tmp_team, TEAM, task_id, 1, "utils.py", "Typo here", "boss", line=10)
        assert c["file"] == "utils.py"
        assert c["line"] == 10
        assert c["body"] == "Typo here"
        assert c["author"] == "boss"
        assert c["task_id"] == task_id
        assert c["attempt"] == 1
        assert "id" in c

    def test_file_level_comment(self, tmp_team, task_id):
        c = add_comment(tmp_team, TEAM, task_id, 1, "README.md", "Needs update", "boss")
        assert c["line"] is None

    def test_multiple_comments_on_same_line(self, tmp_team, task_id):
        add_comment(tmp_team, TEAM, task_id, 1, "app.py", "First", "boss", line=5)
        add_comment(tmp_team, TEAM, task_id, 1, "app.py", "Second", "boss", line=5)
        comments = get_comments(tmp_team, TEAM, task_id, attempt=1)
        line5 = [c for c in comments if c["line"] == 5]
        assert len(line5) == 2


class TestGetComments:
    def test_filter_by_attempt(self, tmp_team, task_id):
        add_comment(tmp_team, TEAM, task_id, 1, "a.py", "Attempt 1", "boss")
        create_review(tmp_team, TEAM, task_id, 2)
        add_comment(tmp_team, TEAM, task_id, 2, "b.py", "Attempt 2", "boss")

        c1 = get_comments(tmp_team, TEAM, task_id, attempt=1)
        c2 = get_comments(tmp_team, TEAM, task_id, attempt=2)
        assert len(c1) == 1
        assert c1[0]["body"] == "Attempt 1"
        assert len(c2) == 1
        assert c2[0]["body"] == "Attempt 2"

    def test_all_attempts(self, tmp_team, task_id):
        add_comment(tmp_team, TEAM, task_id, 1, "a.py", "First", "boss")
        create_review(tmp_team, TEAM, task_id, 2)
        add_comment(tmp_team, TEAM, task_id, 2, "b.py", "Second", "boss")

        all_comments = get_comments(tmp_team, TEAM, task_id, attempt=None)
        assert len(all_comments) == 2
        assert all_comments[0]["attempt"] == 1
        assert all_comments[1]["attempt"] == 2

    def test_empty_for_nonexistent(self, tmp_team):
        assert get_comments(tmp_team, TEAM, 9999) == []


# ---------------------------------------------------------------------------
# API endpoint tests — POST /teams/{team}/tasks/{id}/reviews/comments
# ---------------------------------------------------------------------------

class TestPostReviewCommentAPI:
    def test_add_comment_via_api(self, client, task_id, tmp_team):
        resp = client.post(
            f"/teams/{TEAM}/tasks/{task_id}/reviews/comments",
            json={"file": "src/main.py", "line": 42, "body": "Should use constant"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["file"] == "src/main.py"
        assert data["line"] == 42
        assert data["body"] == "Should use constant"
        assert data["attempt"] == 1

    def test_file_level_comment_via_api(self, client, task_id):
        resp = client.post(
            f"/teams/{TEAM}/tasks/{task_id}/reviews/comments",
            json={"file": "README.md", "body": "Update docs"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["line"] is None

    def test_nonexistent_task_404(self, client):
        resp = client.post(
            f"/teams/{TEAM}/tasks/9999/reviews/comments",
            json={"file": "x.py", "body": "Hello"},
        )
        assert resp.status_code == 404

    def test_no_review_attempt_400(self, client, tmp_team):
        """Cannot post comments on a task with no active review."""
        task = create_task(tmp_team, TEAM, title="No review")
        resp = client.post(
            f"/teams/{TEAM}/tasks/{task['id']}/reviews/comments",
            json={"file": "x.py", "body": "Hello"},
        )
        assert resp.status_code == 400
        assert "no active review" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# API endpoint tests — GET /teams/{team}/tasks/{id}/reviews
# ---------------------------------------------------------------------------

class TestGetReviewsAPI:
    def test_list_reviews_with_comments(self, client, task_id, tmp_team):
        add_comment(tmp_team, TEAM, task_id, 1, "a.py", "Fix", "boss", line=1)
        resp = client.get(f"/teams/{TEAM}/tasks/{task_id}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert len(data[0]["comments"]) == 1

    def test_current_review(self, client, task_id, tmp_team):
        set_verdict(tmp_team, TEAM, task_id, 1, "approved", summary="Ship it")
        resp = client.get(f"/teams/{TEAM}/tasks/{task_id}/reviews/current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["verdict"] == "approved"
        assert data["summary"] == "Ship it"
