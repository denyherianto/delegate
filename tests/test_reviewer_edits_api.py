"""Tests for GET /api/tasks/{task_id}/file and POST /api/tasks/{task_id}/reviewer-edits endpoints."""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from delegate.bootstrap import bootstrap
from delegate.config import add_member
from delegate.repo import register_repo, create_agent_worktree
from delegate.task import create_task, change_status, update_task, get_task
from delegate.web import create_app


TEAM = "testteam"
REPO_NAME = "myproject"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hc_home(tmp_path):
    """Bootstrapped delegate home with a human member."""
    hc = tmp_path / "hc"
    hc.mkdir()
    add_member(hc, "nikhil")
    bootstrap(hc, TEAM, manager="manager", agents=["alice"])
    return hc


@pytest.fixture
def local_repo(tmp_path):
    """A local git repo with main branch and a sample file."""
    repo = tmp_path / REPO_NAME
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=str(repo))
    _git(["config", "user.email", "test@test.com"], cwd=str(repo))
    _git(["config", "user.name", "Test"], cwd=str(repo))
    (repo / "hello.py").write_text("print('hello')\n")
    _git(["add", "."], cwd=str(repo))
    _git(["commit", "-m", "Initial commit"], cwd=str(repo))
    return repo


@pytest.fixture
def registered_repo(hc_home, local_repo):
    """Register the local repo in the team."""
    register_repo(hc_home, TEAM, str(local_repo), name=REPO_NAME)
    return local_repo


@pytest.fixture
def task_on_branch(hc_home, registered_repo):
    """Create a task with a feature branch that has a committed file.

    Returns (task_dict, branch_name, repo_path).
    """
    repo_dir = str(registered_repo)

    # Create a task and manually create the branch
    task = create_task(hc_home, TEAM, title="Review Task", assignee="alice", repo=[REPO_NAME])
    task_id = task["id"]

    branch = f"delegate/test/{TEAM}/T{task_id:04d}"

    # Create the branch on the local repo
    _git(["checkout", "-b", branch], cwd=repo_dir)
    (registered_repo / "feature.py").write_text("x = 1\n")
    _git(["add", "."], cwd=repo_dir)
    _git(
        ["commit", "--author=alice <alice@localhost>", "-m", "Add feature"],
        cwd=repo_dir,
    )
    head_sha = _git(["rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()

    # Go back to main
    _git(["checkout", "main"], cwd=repo_dir)

    # Store branch in the task
    update_task(hc_home, TEAM, task_id, branch=branch)
    task = get_task(hc_home, TEAM, task_id)

    return task, branch, registered_repo, head_sha


@pytest.fixture
def in_review_task(hc_home, task_on_branch):
    """A task_on_branch advanced to in_review status."""
    task, branch, repo_path, head_sha = task_on_branch
    change_status(hc_home, TEAM, task["id"], "in_progress")
    change_status(hc_home, TEAM,task["id"], "in_review")
    task = get_task(hc_home, TEAM, task["id"])
    return task, branch, repo_path, head_sha


@pytest.fixture
def client(hc_home):
    """FastAPI test client."""
    app = create_app(hc_home=hc_home)
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/tasks/{task_id}/file
# ---------------------------------------------------------------------------

class TestGetTaskFile:
    def test_returns_content_and_head_sha(self, client, in_review_task):
        task, branch, repo_path, head_sha = in_review_task
        resp = client.get(f"/api/tasks/{task['id']}/file", params={"path": "feature.py"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "x = 1\n"
        assert data["head_sha"] == head_sha

    def test_returns_correct_head_sha(self, client, in_review_task):
        task, branch, repo_path, head_sha = in_review_task
        resp = client.get(f"/api/tasks/{task['id']}/file", params={"path": "feature.py"})
        data = resp.json()
        # head_sha must be a 40-char hex SHA
        assert len(data["head_sha"]) == 40
        assert all(c in "0123456789abcdef" for c in data["head_sha"])

    def test_nonexistent_file_returns_404(self, client, in_review_task):
        task, branch, repo_path, head_sha = in_review_task
        resp = client.get(f"/api/tasks/{task['id']}/file", params={"path": "nonexistent.py"})
        assert resp.status_code == 404

    def test_nonexistent_task_returns_404(self, client):
        resp = client.get("/api/tasks/9999/file", params={"path": "feature.py"})
        assert resp.status_code == 404

    def test_file_from_initial_commit(self, client, in_review_task):
        """Files present on main that are also on the branch should be readable."""
        task, branch, repo_path, head_sha = in_review_task
        resp = client.get(f"/api/tasks/{task['id']}/file", params={"path": "hello.py"})
        assert resp.status_code == 200
        data = resp.json()
        assert "print('hello')" in data["content"]


# ---------------------------------------------------------------------------
# POST /api/tasks/{task_id}/reviewer-edits
# ---------------------------------------------------------------------------

class TestPostReviewerEdits:
    def test_happy_path_commits_and_returns_new_sha(self, client, in_review_task, registered_repo):
        task, branch, repo_path, head_sha = in_review_task
        resp = client.post(
            f"/api/tasks/{task['id']}/reviewer-edits",
            json={
                "edits": [
                    {
                        "file": "feature.py",
                        "content": "x = 42\n",
                        "expected_sha": head_sha,
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "new_sha" in data
        assert data["new_sha"] != head_sha
        assert len(data["new_sha"]) == 40

        # Verify new content is on the branch
        result = _git(["show", f"{branch}:feature.py"], cwd=str(repo_path))
        assert result.stdout == "x = 42\n"

    def test_stale_sha_returns_409(self, client, in_review_task):
        task, branch, repo_path, head_sha = in_review_task
        resp = client.post(
            f"/api/tasks/{task['id']}/reviewer-edits",
            json={
                "edits": [
                    {
                        "file": "feature.py",
                        "content": "x = 99\n",
                        "expected_sha": "0" * 40,  # wrong sha
                    }
                ]
            },
        )
        assert resp.status_code == 409
        data = resp.json()
        detail = data["detail"]
        assert detail["error"] == "stale"
        assert detail["current_sha"] == head_sha

    def test_no_op_skips_commit(self, client, in_review_task):
        """Editing a file with identical content should skip the commit."""
        task, branch, repo_path, head_sha = in_review_task
        resp = client.post(
            f"/api/tasks/{task['id']}/reviewer-edits",
            json={
                "edits": [
                    {
                        "file": "feature.py",
                        "content": "x = 1\n",  # identical to branch content
                        "expected_sha": head_sha,
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_sha"] == head_sha
        assert data.get("no_changes") is True

        # Branch HEAD should be unchanged
        result = _git(["rev-parse", branch], cwd=str(repo_path))
        assert result.stdout.strip() == head_sha

    def test_wrong_status_returns_403(self, client, task_on_branch):
        """Task in todo or in_progress should get 403."""
        task, branch, repo_path, head_sha = task_on_branch
        # Task is in 'todo' by default
        resp = client.post(
            f"/api/tasks/{task['id']}/reviewer-edits",
            json={
                "edits": [
                    {
                        "file": "feature.py",
                        "content": "x = 1\n",
                        "expected_sha": head_sha,
                    }
                ]
            },
        )
        assert resp.status_code == 403
        assert "in_review" in resp.json()["detail"] or "in_approval" in resp.json()["detail"]

    def test_in_approval_status_accepted(self, client, task_on_branch, hc_home):
        """Tasks in in_approval should also be editable."""
        task, branch, repo_path, head_sha = task_on_branch
        change_status(hc_home, TEAM, task["id"], "in_progress")
        change_status(hc_home, TEAM, task["id"], "in_review")
        change_status(hc_home, TEAM, task["id"], "in_approval")

        resp = client.post(
            f"/api/tasks/{task['id']}/reviewer-edits",
            json={
                "edits": [
                    {
                        "file": "feature.py",
                        "content": "x = 100\n",
                        "expected_sha": head_sha,
                    }
                ]
            },
        )
        assert resp.status_code == 200
        assert "new_sha" in resp.json()

    def test_nonexistent_task_returns_404(self, client):
        resp = client.post(
            "/api/tasks/9999/reviewer-edits",
            json={"edits": [{"file": "x.py", "content": "y\n", "expected_sha": "a" * 40}]},
        )
        assert resp.status_code == 404

    def test_multiple_edits_in_one_commit(self, client, in_review_task, registered_repo):
        """Multiple files can be committed in one call."""
        task, branch, repo_path, head_sha = in_review_task
        resp = client.post(
            f"/api/tasks/{task['id']}/reviewer-edits",
            json={
                "edits": [
                    {"file": "feature.py", "content": "x = 42\n", "expected_sha": head_sha},
                    {"file": "hello.py", "content": "print('world')\n", "expected_sha": head_sha},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "new_sha" in data

        # Both files updated on branch
        r1 = _git(["show", f"{branch}:feature.py"], cwd=str(repo_path))
        assert r1.stdout == "x = 42\n"
        r2 = _git(["show", f"{branch}:hello.py"], cwd=str(repo_path))
        assert r2.stdout == "print('world')\n"
