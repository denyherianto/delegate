"""Tests for the POST /projects endpoint -- tilde expansion in repo paths."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from delegate.web import create_app


@pytest.fixture
def client(tmp_team):
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


class TestCreateProjectRepoPath:
    def test_tilde_path_error_shows_original_path(self, client):
        """Error for non-existent tilde path must echo back the tilde form, not expanded."""
        resp = client.post("/projects", json={
            "name": "tilde-proj",
            "repo_path": "~/no-such-dir-xyzzy-12345",
            "agent_count": 1,
            "model": "sonnet",
        })
        assert resp.status_code == 400
        # User sees the path they typed, not the expanded absolute path
        assert "~/no-such-dir-xyzzy-12345" in resp.json()["detail"]

    def test_absolute_nonexistent_path_rejected(self, client):
        """Absolute paths that do not exist are rejected with a 400."""
        resp = client.post("/projects", json={
            "name": "abs-proj",
            "repo_path": "/no/such/path/xyz",
            "agent_count": 1,
            "model": "sonnet",
        })
        assert resp.status_code == 400
        assert "/no/such/path/xyz" in resp.json()["detail"]

    def test_tilde_expands_before_is_dir_check(self):
        """Unit test: Path(tilde_path).expanduser() resolves ~ to home dir."""
        home = Path.home()
        expanded = Path("~/").expanduser()
        assert expanded == home

        # Simulate what the fixed endpoint does: expand before is_dir
        tilde_path = "~"
        expanded = str(Path(tilde_path).expanduser())
        assert not expanded.startswith("~")
        assert expanded == str(home)
