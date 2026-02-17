"""Tests for PWA endpoints: /manifest.json and /sw.js."""

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from delegate.web import create_app


SW_CONTENT = 'self.addEventListener("fetch", () => {});'

# _static_dir in web.py is always Path(__file__).parent / "static" (the delegate package static dir)
_STATIC_DIR = Path(__file__).parent.parent / "delegate" / "static"


@pytest.fixture
def sw_file(tmp_path):
    """Place a sw.js in the package static dir for the duration of the test."""
    _STATIC_DIR.mkdir(exist_ok=True)
    sw_path = _STATIC_DIR / "sw.js"
    existed = sw_path.exists()
    original = sw_path.read_bytes() if existed else None
    sw_path.write_text(SW_CONTENT)
    yield sw_path
    # Restore original state
    if existed:
        sw_path.write_bytes(original)
    else:
        sw_path.unlink(missing_ok=True)


@pytest.fixture
def client(tmp_team):
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


class TestManifest:
    def test_manifest_returns_200(self, client):
        resp = client.get("/manifest.json")
        assert resp.status_code == 200

    def test_manifest_default_port_name(self, client, monkeypatch):
        monkeypatch.setenv("DELEGATE_PORT", "3548")
        resp = client.get("/manifest.json")
        assert resp.json()["name"] == "Delegate"

    def test_manifest_non_default_port_name(self, client, monkeypatch):
        monkeypatch.setenv("DELEGATE_PORT", "4000")
        resp = client.get("/manifest.json")
        assert resp.json()["name"] == "Delegate :4000"

    def test_manifest_required_fields(self, client, monkeypatch):
        monkeypatch.setenv("DELEGATE_PORT", "3548")
        data = client.get("/manifest.json").json()
        assert data["display"] == "standalone"
        assert data["start_url"] == "/"
        assert data["background_color"] == "#1e1e1e"
        assert data["theme_color"] == "#1e1e1e"
        assert len(data["icons"]) == 2

    def test_manifest_icon_sizes(self, client):
        data = client.get("/manifest.json").json()
        sizes = {icon["sizes"] for icon in data["icons"]}
        assert "192x192" in sizes
        assert "512x512" in sizes


class TestServiceWorker:
    def test_sw_returns_200(self, client, sw_file):
        resp = client.get("/sw.js")
        assert resp.status_code == 200

    def test_sw_content_type(self, client, sw_file):
        resp = client.get("/sw.js")
        assert "javascript" in resp.headers["content-type"]

    def test_sw_content(self, client, sw_file):
        resp = client.get("/sw.js")
        assert "fetch" in resp.text
