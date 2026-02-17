"""Tests for PWA endpoints: /manifest.json and /sw.js."""

import os
import pytest
from fastapi.testclient import TestClient

from delegate.web import create_app


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
    def test_sw_returns_200(self, client):
        resp = client.get("/sw.js")
        assert resp.status_code == 200

    def test_sw_content_type(self, client):
        resp = client.get("/sw.js")
        assert "javascript" in resp.headers["content-type"]

    def test_sw_content(self, client):
        resp = client.get("/sw.js")
        assert "fetch" in resp.text
