"""Tests for GET /api/files/complete and GET /api/tasks/{task_id}/files/complete."""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from delegate.bootstrap import bootstrap
from delegate.config import add_member
from delegate.repo import register_repo
from delegate.task import create_task, change_status, update_task, get_task
from delegate.web import create_app


TEAM = "testteam"
REPO_NAME = "myproject"


# ---------------------------------------------------------------------------
# Helpers
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
def client(hc_home):
    """FastAPI test client."""
    app = create_app(hc_home=hc_home)
    return TestClient(app)


@pytest.fixture
def worktree_task(hc_home, registered_repo):
    """Create a task with a real worktree on disk.

    Advances the task to in_progress so the worktree exists and is active.
    Returns (task_dict, worktree_root_path).
    """
    from delegate.paths import task_worktree_dir

    task = create_task(hc_home, TEAM, title="Test Task", assignee="alice", repo=[REPO_NAME])
    task_id = task["id"]
    branch = f"delegate/test/{TEAM}/T{task_id:04d}"

    repo_dir = str(registered_repo)
    _git(["checkout", "-b", branch], cwd=repo_dir)
    (registered_repo / "main.py").write_text("x = 1\n")
    _git(["add", "."], cwd=repo_dir)
    _git(["commit", "--author=alice <alice@localhost>", "-m", "Add main.py"], cwd=repo_dir)
    _git(["checkout", "main"], cwd=repo_dir)

    update_task(hc_home, TEAM, task_id, branch=branch)
    change_status(hc_home, TEAM, task_id, "in_progress")

    # Create the worktree directory and populate it with some files
    wt_root = task_worktree_dir(hc_home, TEAM, REPO_NAME, task_id)
    wt_root.mkdir(parents=True, exist_ok=True)

    # Simulate worktree contents
    (wt_root / "main.py").write_text("x = 1\n")
    (wt_root / "README.md").write_text("# readme\n")
    src = wt_root / "src"
    src.mkdir()
    (src / "utils.py").write_text("# utils\n")
    (src / "api.py").write_text("# api\n")

    task = get_task(hc_home, TEAM, task_id)
    return task, wt_root


# ---------------------------------------------------------------------------
# GET /api/files/complete
# ---------------------------------------------------------------------------

class TestGlobalFilesComplete:
    def test_empty_path_returns_home_dir(self, client):
        """Empty path defaults to the user's home directory listing."""
        resp = client.get("/api/files/complete", params={"path": ""})
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        # Each entry path must be absolute and start with the home directory
        home = str(Path.home())
        for e in entries:
            assert e["path"].startswith(home), (
                f"Expected entry under home dir {home!r}, got {e['path']!r}"
            )

    def test_missing_path_param_returns_home_dir(self, client):
        """Omitting path entirely defaults to the user's home directory listing."""
        resp = client.get("/api/files/complete")
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        home = str(Path.home())
        for e in entries:
            assert e["path"].startswith(home), (
                f"Expected entry under home dir {home!r}, got {e['path']!r}"
            )

    def test_requires_absolute_path(self, client, tmp_path):
        """Relative paths are rejected with 400."""
        resp = client.get("/api/files/complete", params={"path": "relative/path"})
        assert resp.status_code == 400

    def test_path_traversal_rejected(self, client, tmp_path):
        """Paths with .. components are rejected with 400."""
        resp = client.get("/api/files/complete", params={"path": "/foo/../etc/passwd"})
        assert resp.status_code == 400

    def test_lists_entries_by_prefix(self, client, tmp_path):
        """Lists filesystem entries matching the absolute prefix."""
        (tmp_path / "alpha.py").write_text("a")
        (tmp_path / "alpha2.py").write_text("b")
        (tmp_path / "beta.py").write_text("c")

        prefix = str(tmp_path / "alpha")
        resp = client.get("/api/files/complete", params={"path": prefix})
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        paths = [e["path"] for e in entries]
        assert str(tmp_path / "alpha.py") in paths
        assert str(tmp_path / "alpha2.py") in paths
        # beta.py should NOT appear
        assert str(tmp_path / "beta.py") not in paths

    def test_dirs_sorted_before_files(self, client, tmp_path):
        """Directories appear before files in the result."""
        (tmp_path / "adir").mkdir()
        (tmp_path / "afile.txt").write_text("x")
        (tmp_path / "bdir").mkdir()

        prefix = str(tmp_path) + "/"
        resp = client.get("/api/files/complete", params={"path": prefix})
        assert resp.status_code == 200
        entries = resp.json()["entries"]

        dirs = [e for e in entries if e["is_dir"]]
        files = [e for e in entries if not e["is_dir"]]
        if dirs and files:
            last_dir_idx = max(entries.index(d) for d in dirs)
            first_file_idx = min(entries.index(f) for f in files)
            assert last_dir_idx < first_file_idx

    def test_is_dir_field(self, client, tmp_path):
        """is_dir is True for directories, False for files."""
        (tmp_path / "mydir").mkdir()
        (tmp_path / "myfile.txt").write_text("x")

        prefix = str(tmp_path) + "/"
        resp = client.get("/api/files/complete", params={"path": prefix})
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        # Use basename for lookup (avoids symlink-resolved path differences on macOS)
        by_name = {e["path"].split("/")[-1]: e for e in entries}
        assert by_name["mydir"]["is_dir"] is True
        assert by_name["myfile.txt"]["is_dir"] is False

    def test_limit_respected(self, client, tmp_path):
        """Result is capped at the requested limit."""
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_text("x")

        prefix = str(tmp_path) + "/"
        resp = client.get("/api/files/complete", params={"path": prefix, "limit": 3})
        assert resp.status_code == 200
        assert len(resp.json()["entries"]) <= 3

    def test_limit_max_50(self, client, tmp_path):
        """limit is capped at 50 even if a larger value is requested."""
        for i in range(60):
            (tmp_path / f"file{i:03d}.txt").write_text("x")

        prefix = str(tmp_path) + "/"
        resp = client.get("/api/files/complete", params={"path": prefix, "limit": 100})
        assert resp.status_code == 200
        assert len(resp.json()["entries"]) <= 50

    def test_nonexistent_prefix_returns_empty(self, client, tmp_path):
        """A prefix pointing to a nonexistent directory returns an empty list."""
        prefix = str(tmp_path / "doesnotexist") + "/"
        resp = client.get("/api/files/complete", params={"path": prefix})
        assert resp.status_code == 200
        assert resp.json()["entries"] == []


# ---------------------------------------------------------------------------
# GET /api/tasks/{task_id}/files/complete
# ---------------------------------------------------------------------------

class TestTaskFilesComplete:
    def test_404_for_task_without_worktree(self, client, hc_home, registered_repo):
        """Returns 404 for a task that is not in an active status."""
        task = create_task(hc_home, TEAM, title="Inactive task", assignee="alice", repo=[REPO_NAME])
        # Task is in 'todo' — no worktree
        resp = client.get(f"/api/tasks/{task['id']}/files/complete")
        assert resp.status_code == 404

    def test_404_for_unknown_task(self, client):
        """Returns 404 for a task ID that does not exist."""
        resp = client.get("/api/tasks/99999/files/complete")
        assert resp.status_code == 404

    def test_path_traversal_rejected(self, client, worktree_task):
        """q values with .. components are rejected with 400."""
        task, _ = worktree_task
        resp = client.get(
            f"/api/tasks/{task['id']}/files/complete",
            params={"q": "../etc/passwd"},
        )
        assert resp.status_code == 400

    def test_empty_q_lists_top_level(self, client, worktree_task):
        """Empty q lists top-level worktree entries."""
        task, wt_root = worktree_task
        resp = client.get(f"/api/tasks/{task['id']}/files/complete", params={"q": ""})
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        paths = [e["path"] for e in entries]
        # src/ dir and root files should appear
        assert any(p == "src" for p in paths)
        assert any(p == "main.py" for p in paths)
        assert any(p == "README.md" for p in paths)

    def test_returns_relative_paths(self, client, worktree_task):
        """Paths in the response are relative to the worktree root."""
        task, wt_root = worktree_task
        resp = client.get(f"/api/tasks/{task['id']}/files/complete", params={"q": "src/"})
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        for e in entries:
            # Must be relative (not starting with /)
            assert not e["path"].startswith("/"), f"Expected relative path, got {e['path']!r}"

    def test_prefix_filter_works(self, client, worktree_task):
        """q prefix correctly filters entries."""
        task, wt_root = worktree_task
        resp = client.get(f"/api/tasks/{task['id']}/files/complete", params={"q": "src/ut"})
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        paths = [e["path"] for e in entries]
        assert "src/utils.py" in paths
        # api.py doesn't start with "ut"
        assert "src/api.py" not in paths

    def test_dirs_sorted_before_files(self, client, worktree_task):
        """Directories appear before files in the result."""
        task, wt_root = worktree_task
        resp = client.get(f"/api/tasks/{task['id']}/files/complete", params={"q": ""})
        assert resp.status_code == 200
        entries = resp.json()["entries"]

        dirs = [e for e in entries if e["is_dir"]]
        files = [e for e in entries if not e["is_dir"]]
        if dirs and files:
            last_dir_idx = max(entries.index(d) for d in dirs)
            first_file_idx = min(entries.index(f) for f in files)
            assert last_dir_idx < first_file_idx

    def test_limit_respected(self, client, worktree_task):
        """Result is capped at the requested limit."""
        task, wt_root = worktree_task
        resp = client.get(
            f"/api/tasks/{task['id']}/files/complete",
            params={"q": "", "limit": 1},
        )
        assert resp.status_code == 200
        assert len(resp.json()["entries"]) <= 1
