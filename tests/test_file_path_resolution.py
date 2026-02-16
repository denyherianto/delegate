"""Tests for file path resolution in delegate/web.py.

Verifies that the backend _resolve_file_path() correctly handles:
1. Absolute paths (start with /) - used directly
2. Delegate-relative paths (no leading /) - resolved from ~/.delegate
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from delegate.web import create_app

TEAM = "testteam"


@pytest.fixture
def client(tmp_team):
    """Create a FastAPI test client using a bootstrapped team directory."""
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


@pytest.fixture
def test_file(tmp_team):
    """Create a test file in the team's shared directory."""
    shared_dir = tmp_team / "teams" / TEAM / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    test_file_path = shared_dir / "test-path-resolution.md"
    test_file_path.write_text("Test content for path resolution")
    return test_file_path


class TestFilePathResolution:
    """Test file path resolution via the /teams/{team}/files/content endpoint."""

    def test_absolute_path(self, client, test_file):
        """Absolute paths should be used directly."""
        # Absolute path to the test file
        abs_path = str(test_file.resolve())
        r = client.get(f"/teams/{TEAM}/files/content", params={"path": abs_path})
        assert r.status_code == 200
        data = r.json()
        assert data["content_type"] == "text/plain"
        assert "Test content for path resolution" in data["content"]

    def test_delegate_relative_path(self, client, test_file, tmp_team):
        """Delegate-relative paths should be resolved from hc_home."""
        # Path relative to hc_home
        rel_path = f"teams/{TEAM}/shared/test-path-resolution.md"
        r = client.get(f"/teams/{TEAM}/files/content", params={"path": rel_path})
        assert r.status_code == 200
        data = r.json()
        assert data["content_type"] == "text/plain"
        assert "Test content for path resolution" in data["content"]

    def test_team_relative_path(self, client, test_file):
        """Delegate-relative paths starting with teams/{team}/ should resolve correctly."""
        # Full delegate-relative path including team
        rel_path = f"teams/{TEAM}/shared/test-path-resolution.md"
        r = client.get(f"/teams/{TEAM}/files/content", params={"path": rel_path})
        assert r.status_code == 200
        data = r.json()
        assert "Test content for path resolution" in data["content"]

    def test_nonexistent_file(self, client):
        """Non-existent files should return 404."""
        r = client.get(f"/teams/{TEAM}/files/content", params={"path": "teams/testteam/shared/nonexistent.md"})
        assert r.status_code == 404
        assert "File not found" in r.json()["detail"]

    def test_absolute_nonexistent_file(self, client):
        """Non-existent absolute paths should return 404."""
        r = client.get(f"/teams/{TEAM}/files/content", params={"path": "/tmp/nonexistent-file-12345.md"})
        assert r.status_code == 404
        assert "File not found" in r.json()["detail"]
