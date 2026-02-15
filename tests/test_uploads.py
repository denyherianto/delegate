"""Tests for file upload endpoints."""

import io
import pytest
from fastapi.testclient import TestClient

from delegate.web import create_app

TEAM = "testteam"


# Test file content fixtures
PNG_1x1 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)

JPEG_1x1 = (
    b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c'
    b'\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c'
    b'\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08'
    b'\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\t\xff\xc4\x00\x14\x10'
    b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\xdf\xff\xd9'
)


@pytest.fixture
def client(tmp_team):
    """Create a FastAPI test client with a bootstrapped team root."""
    app = create_app(hc_home=tmp_team)
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /teams/{team}/uploads
# ---------------------------------------------------------------------------


class TestUploadEndpoint:
    def test_upload_valid_png_succeeds(self, client, tmp_team):
        """Upload a valid PNG file returns 200 with metadata."""
        files = {"files": ("test.png", io.BytesIO(PNG_1x1), "image/png")}
        resp = client.post(f"/teams/{TEAM}/uploads", files=files)

        assert resp.status_code == 200
        data = resp.json()
        assert "uploaded" in data
        assert len(data["uploaded"]) == 1

        uploaded = data["uploaded"][0]
        assert uploaded["original_name"] == "test.png"
        assert uploaded["stored_path"].startswith("uploads/")
        assert uploaded["url"].startswith(f"/teams/{TEAM}/uploads/")
        assert uploaded["size_bytes"] == len(PNG_1x1)
        assert uploaded["mime_type"] == "image/png"

        # Verify file exists on disk
        from pathlib import Path
        from delegate.paths import team_dir
        team_path = team_dir(tmp_team, TEAM)
        file_path = team_path / uploaded["stored_path"]
        assert file_path.exists()
        assert file_path.read_bytes() == PNG_1x1

    def test_upload_valid_jpeg_succeeds(self, client, tmp_team):
        """Upload a valid JPEG file returns 200 with metadata."""
        files = {"files": ("photo.jpg", io.BytesIO(JPEG_1x1), "image/jpeg")}
        resp = client.post(f"/teams/{TEAM}/uploads", files=files)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["uploaded"]) == 1

        uploaded = data["uploaded"][0]
        assert uploaded["original_name"] == "photo.jpg"
        assert uploaded["mime_type"] == "image/jpeg"

        # Verify file exists
        from pathlib import Path
        from delegate.paths import team_dir
        team_path = team_dir(tmp_team, TEAM)
        file_path = team_path / uploaded["stored_path"]
        assert file_path.exists()

    def test_upload_text_file_succeeds(self, client, tmp_team):
        """Upload a valid JSON text file succeeds."""
        json_content = b'{"key": "value"}'
        files = {"files": ("data.json", io.BytesIO(json_content), "application/json")}
        resp = client.post(f"/teams/{TEAM}/uploads", files=files)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["uploaded"]) == 1

        uploaded = data["uploaded"][0]
        assert uploaded["original_name"] == "data.json"
        # Text files don't have magic bytes, so mime_type is None
        assert uploaded["mime_type"] is None or uploaded["mime_type"] == ""

        # Verify file exists
        from delegate.paths import team_dir
        team_path = team_dir(tmp_team, TEAM)
        file_path = team_path / uploaded["stored_path"]
        assert file_path.exists()
        assert file_path.read_bytes() == json_content

    def test_upload_invalid_extension_fails(self, client):
        """Upload with invalid extension (.exe) returns 400."""
        files = {"files": ("malware.exe", io.BytesIO(b"fake executable"), "application/octet-stream")}
        resp = client.post(f"/teams/{TEAM}/uploads", files=files)

        assert resp.status_code == 400
        assert "Invalid file type" in resp.json()["detail"]

    def test_upload_file_too_large_fails(self, client):
        """Upload file exceeding 50MB limit returns 400."""
        from delegate.uploads import MAX_FILE_SIZE
        # Create a file slightly larger than MAX_FILE_SIZE
        large_content = b"x" * (MAX_FILE_SIZE + 1)
        files = {"files": ("large.txt", io.BytesIO(large_content), "text/plain")}
        resp = client.post(f"/teams/{TEAM}/uploads", files=files)

        assert resp.status_code == 400
        assert "too large" in resp.json()["detail"].lower()

    def test_upload_total_size_exceeds_limit_fails(self, client):
        """Upload multiple files exceeding 200MB total returns 413."""
        from delegate.uploads import MAX_TOTAL_SIZE
        # Create files that together exceed MAX_TOTAL_SIZE
        file_size = (MAX_TOTAL_SIZE // 2) + 1
        content1 = b"a" * file_size
        content2 = b"b" * file_size

        files = [
            ("files", ("file1.txt", io.BytesIO(content1), "text/plain")),
            ("files", ("file2.txt", io.BytesIO(content2), "text/plain")),
        ]
        resp = client.post(f"/teams/{TEAM}/uploads", files=files)

        assert resp.status_code == 413
        assert "Total upload size exceeds limit" in resp.json()["detail"]

    def test_upload_multiple_files_succeeds(self, client, tmp_team):
        """Upload multiple files in one request succeeds."""
        files = [
            ("files", ("image1.png", io.BytesIO(PNG_1x1), "image/png")),
            ("files", ("image2.png", io.BytesIO(PNG_1x1), "image/png")),
            ("files", ("data.json", io.BytesIO(b'{"test": true}'), "application/json")),
        ]
        resp = client.post(f"/teams/{TEAM}/uploads", files=files)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["uploaded"]) == 3

        # Verify all files exist
        from delegate.paths import team_dir
        team_path = team_dir(tmp_team, TEAM)
        for uploaded in data["uploaded"]:
            file_path = team_path / uploaded["stored_path"]
            assert file_path.exists()

    def test_upload_sanitizes_filename(self, client, tmp_team):
        """Upload with special characters in filename sanitizes it."""
        files = {"files": ("My Screenshot 2026.png", io.BytesIO(PNG_1x1), "image/png")}
        resp = client.post(f"/teams/{TEAM}/uploads", files=files)

        assert resp.status_code == 200
        data = resp.json()
        uploaded = data["uploaded"][0]

        # Filename should be sanitized: lowercase, spaces->hyphens
        assert "my-screenshot-2026" in uploaded["stored_path"]
        assert uploaded["stored_path"].endswith(".png")

    def test_upload_wrong_magic_bytes_fails(self, client):
        """Upload with .jpg extension but PNG magic bytes fails."""
        # PNG magic bytes but .jpg extension
        files = {"files": ("fake.jpg", io.BytesIO(PNG_1x1), "image/jpeg")}
        resp = client.post(f"/teams/{TEAM}/uploads", files=files)

        assert resp.status_code == 400
        # Should fail MIME validation
        assert "MIME type" in resp.json()["detail"] or "does not match" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /teams/{team}/uploads/{year}/{month}/{filename}
# ---------------------------------------------------------------------------


class TestServeEndpoint:
    def test_serve_uploaded_file_succeeds(self, client, tmp_team):
        """Serve an uploaded file returns correct content and headers."""
        # First upload a file
        files = {"files": ("test.png", io.BytesIO(PNG_1x1), "image/png")}
        upload_resp = client.post(f"/teams/{TEAM}/uploads", files=files)
        assert upload_resp.status_code == 200

        uploaded = upload_resp.json()["uploaded"][0]
        url = uploaded["url"]

        # Now fetch it
        serve_resp = client.get(url)
        assert serve_resp.status_code == 200
        assert serve_resp.content == PNG_1x1
        assert serve_resp.headers["content-type"] == "image/png"
        assert serve_resp.headers["x-content-type-options"] == "nosniff"
        assert "max-age=86400" in serve_resp.headers["cache-control"]

    def test_serve_image_has_inline_disposition(self, client, tmp_team):
        """Serve image file has Content-Disposition: inline."""
        files = {"files": ("photo.jpg", io.BytesIO(JPEG_1x1), "image/jpeg")}
        upload_resp = client.post(f"/teams/{TEAM}/uploads", files=files)
        uploaded = upload_resp.json()["uploaded"][0]

        serve_resp = client.get(uploaded["url"])
        assert serve_resp.status_code == 200
        assert serve_resp.headers["content-disposition"] == "inline"

    def test_serve_svg_has_attachment_disposition(self, client, tmp_team):
        """Serve SVG file has Content-Disposition: attachment for XSS prevention."""
        # Minimal SVG content
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        files = {"files": ("icon.svg", io.BytesIO(svg_content), "image/svg+xml")}
        upload_resp = client.post(f"/teams/{TEAM}/uploads", files=files)
        uploaded = upload_resp.json()["uploaded"][0]

        serve_resp = client.get(uploaded["url"])
        assert serve_resp.status_code == 200
        # SVG should be forced to download, not inline
        assert "attachment" in serve_resp.headers["content-disposition"]
        assert "icon" in serve_resp.headers["content-disposition"]

    def test_serve_svg_has_csp_header(self, client, tmp_team):
        """Serve SVG file has Content-Security-Policy header."""
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        files = {"files": ("icon.svg", io.BytesIO(svg_content), "image/svg+xml")}
        upload_resp = client.post(f"/teams/{TEAM}/uploads", files=files)
        uploaded = upload_resp.json()["uploaded"][0]

        serve_resp = client.get(uploaded["url"])
        assert serve_resp.status_code == 200
        assert "content-security-policy" in serve_resp.headers
        assert "default-src 'none'" in serve_resp.headers["content-security-policy"]

    def test_serve_path_traversal_attempt_fails(self, client, tmp_team):
        """Serve with path traversal in filename parameter returns 403."""
        from pathlib import Path
        from delegate.paths import team_dir

        # Create a secret file outside uploads dir
        team_path = team_dir(tmp_team, TEAM)
        secret_file = team_path / "secrets.txt"
        secret_file.write_text("secret data")

        # Try accessing with ".." in the filename - our safe_path should catch it
        # Note: FastAPI normalizes URL paths, so we test the safe_path function directly
        from delegate.uploads import safe_path
        uploads_dir = team_path / "uploads"

        # This should fail because it tries to escape uploads dir
        result = safe_path(uploads_dir, "2026/02/../../secrets.txt")
        assert result is None  # safe_path returns None for invalid paths

    def test_serve_nonexistent_file_fails(self, client):
        """Serve nonexistent file returns 404."""
        url = f"/teams/{TEAM}/uploads/2026/02/nonexistent.png"
        resp = client.get(url)

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_serve_text_file_has_attachment_disposition(self, client, tmp_team):
        """Serve text file (not image/pdf) has Content-Disposition: attachment."""
        files = {"files": ("data.json", io.BytesIO(b'{"key": "value"}'), "application/json")}
        upload_resp = client.post(f"/teams/{TEAM}/uploads", files=files)
        uploaded = upload_resp.json()["uploaded"][0]

        serve_resp = client.get(uploaded["url"])
        assert serve_resp.status_code == 200
        # JSON should be downloaded, not shown inline
        assert "attachment" in serve_resp.headers["content-disposition"]
        assert "data" in serve_resp.headers["content-disposition"]
