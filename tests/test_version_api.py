"""Tests for GET /api/version endpoint."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import tomllib

import pytest
from fastapi.testclient import TestClient

from delegate.web import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_team):
    """FastAPI test client with a bootstrapped team."""
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


def _make_pypi_response(version: str) -> MagicMock:
    """Build a mock urllib response that returns a PyPI-shaped JSON body."""
    body = json.dumps({"info": {"version": version}}).encode()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVersionEndpoint:
    def test_returns_200_with_required_fields(self, client):
        """GET /api/version returns 200 with current, latest, update_available."""
        with patch("urllib.request.urlopen", return_value=_make_pypi_response("99.99.99")):
            resp = client.get("/api/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "current" in data
        assert "latest" in data
        assert "update_available" in data

    def test_update_available_true_when_latest_greater(self, client):
        """update_available is True when latest version is newer than current."""
        with patch("urllib.request.urlopen", return_value=_make_pypi_response("99.99.99")):
            resp = client.get("/api/version")
        data = resp.json()
        assert data["latest"] == "99.99.99"
        assert data["update_available"] is True

    def test_update_available_false_when_versions_equal(self, client):
        """update_available is False when latest == current."""
        # First, get the real current version
        from importlib.metadata import version as pkg_version
        current = pkg_version("delegate-ai")

        with patch("urllib.request.urlopen", return_value=_make_pypi_response(current)):
            resp = client.get("/api/version")
        data = resp.json()
        assert data["latest"] == current
        assert data["update_available"] is False

    def test_pypi_fetch_failure_returns_gracefully(self, client):
        """On PyPI fetch failure, latest is null and update_available is false."""
        with patch("urllib.request.urlopen", side_effect=OSError("network error")):
            resp = client.get("/api/version")
        assert resp.status_code == 200
        data = resp.json()
        assert data["latest"] is None
        assert data["update_available"] is False
        assert data["current"] is not None  # current version still returned

    def test_cache_prevents_second_http_request(self, tmp_team):
        """Second call within 1 hour uses cached result — no second HTTP request."""
        app = create_app(hc_home=tmp_team)
        # Each create_app() call gets a fresh _pypi_cache dict, so we control it here.
        c = TestClient(app)

        call_count = 0

        def fake_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            return _make_pypi_response("99.99.99")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            c.get("/api/version")
            c.get("/api/version")

        assert call_count == 1, f"Expected 1 HTTP call, got {call_count}"

    def test_current_version_is_a_string(self, client):
        """current field is a non-empty string."""
        with patch("urllib.request.urlopen", return_value=_make_pypi_response("1.0.0")):
            resp = client.get("/api/version")
        data = resp.json()
        assert isinstance(data["current"], str)
        assert len(data["current"]) > 0

    def test_timeout_failure_handled_gracefully(self, client):
        """Timeout from urllib is handled — returns latest: null."""
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            resp = client.get("/api/version")
        assert resp.status_code == 200
        data = resp.json()
        assert data["latest"] is None
        assert data["update_available"] is False

    def test_falls_back_to_pyproject_when_metadata_unavailable(self, client):
        """When importlib.metadata raises PackageNotFoundError, version is read from pyproject.toml."""
        from importlib.metadata import PackageNotFoundError

        # Read the expected version directly from pyproject.toml
        _pyproject = Path(__file__).parent.parent / "pyproject.toml"
        with open(_pyproject, "rb") as f:
            expected_version = tomllib.load(f)["project"]["version"]

        with patch("importlib.metadata.version", side_effect=PackageNotFoundError("delegate-ai")):
            with patch("urllib.request.urlopen", return_value=_make_pypi_response("1.0.0")):
                resp = client.get("/api/version")

        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] == expected_version

    def test_falls_back_to_unknown_when_both_metadata_and_pyproject_fail(self, client):
        """When both importlib.metadata and pyproject.toml read fail, current is 'unknown'."""
        from importlib.metadata import PackageNotFoundError

        with patch("importlib.metadata.version", side_effect=PackageNotFoundError("delegate-ai")):
            with patch("builtins.open", side_effect=OSError("no such file")):
                with patch("urllib.request.urlopen", return_value=_make_pypi_response("1.0.0")):
                    resp = client.get("/api/version")

        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] == "unknown"
