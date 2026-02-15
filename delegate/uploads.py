"""File upload utilities for the Delegate web app.

Provides:
    - File validation (extension + magic bytes)
    - Sanitized filename generation with collision handling
    - Temp-file-then-move pattern for safe writes
"""

import hashlib
import re
import time
import uuid
from pathlib import Path

import filetype


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "webp", "svg",
    "pdf", "md", "txt", "csv", "json", "yaml", "yml",
    "zip", "html", "css", "js", "py"
}

# Text-based files that don't have magic bytes
TEXT_EXTENSIONS = {
    "md", "txt", "csv", "json", "yaml", "yml",
    "html", "css", "js", "py", "svg"
}

# Size limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_TOTAL_SIZE = 200 * 1024 * 1024  # 200 MB


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_file(content: bytes, filename: str) -> tuple[bool, str | None, str]:
    """Validate file extension and MIME type.

    Args:
        content: File content as bytes
        filename: Original filename

    Returns:
        Tuple of (is_valid, mime_type, error_message)
        - is_valid: True if file passes validation
        - mime_type: Detected MIME type (or None for text files)
        - error_message: Error message if validation fails, empty string if valid
    """
    # Extract extension
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    # Check extension allowlist
    if ext not in ALLOWED_EXTENSIONS:
        return False, None, f"Invalid file type: .{ext}"

    # For text files, skip magic bytes check (filetype returns None for text)
    if ext in TEXT_EXTENSIONS:
        return True, None, ""

    # For binary files, verify magic bytes match extension
    kind = filetype.guess(content)
    if kind is None:
        return False, None, f"Could not detect file type for .{ext} file"

    mime_type = kind.mime

    # Validate MIME type matches extension
    # Note: Some extensions have multiple valid MIME types
    if ext in ("jpg", "jpeg") and mime_type == "image/jpeg":
        return True, mime_type, ""
    elif ext == "png" and mime_type == "image/png":
        return True, mime_type, ""
    elif ext == "gif" and mime_type == "image/gif":
        return True, mime_type, ""
    elif ext == "webp" and mime_type == "image/webp":
        return True, mime_type, ""
    elif ext == "svg" and mime_type == "image/svg+xml":
        return True, mime_type, ""
    elif ext == "pdf" and mime_type == "application/pdf":
        return True, mime_type, ""
    elif ext == "zip" and mime_type == "application/zip":
        return True, mime_type, ""
    else:
        return False, None, f"MIME type {mime_type} does not match extension .{ext}"


def validate_file_size(size: int) -> tuple[bool, str]:
    """Validate file size against limits.

    Args:
        size: File size in bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    if size > MAX_FILE_SIZE:
        return False, f"File too large: {size} bytes (max {MAX_FILE_SIZE})"
    return True, ""


# ---------------------------------------------------------------------------
# Filename Sanitization
# ---------------------------------------------------------------------------

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage.

    - Lowercase
    - Spaces to hyphens
    - Strip special chars (keep alphanumeric, hyphens, underscores, dots)
    - Max 50 chars before extension

    Args:
        filename: Original filename

    Returns:
        Sanitized filename (without extension)
    """
    # Split into name and extension
    if "." in filename:
        name, ext = filename.rsplit(".", 1)
    else:
        name, ext = filename, ""

    # Lowercase
    name = name.lower()

    # Replace spaces with hyphens
    name = name.replace(" ", "-")

    # Keep only alphanumeric, hyphens, underscores
    name = re.sub(r"[^a-z0-9\-_]", "", name)

    # Limit length
    name = name[:50]

    # Remove trailing hyphens/underscores
    name = name.rstrip("-_")

    # If empty after sanitization, use "file"
    if not name:
        name = "file"

    return name


def generate_filename(original_filename: str) -> str:
    """Generate a unique filename with hash.

    Pattern: <sanitized-name>-<hash6>.<ext>

    Args:
        original_filename: Original filename from upload

    Returns:
        Generated filename
    """
    # Extract extension
    if "." in original_filename:
        ext = original_filename.rsplit(".", 1)[1].lower()
    else:
        ext = "bin"

    # Sanitize base name
    sanitized = sanitize_filename(original_filename)

    # Generate hash from original filename + timestamp
    timestamp_ms = int(time.time() * 1000)
    hash_input = f"{original_filename}{timestamp_ms}".encode("utf-8")
    hash_hex = hashlib.sha256(hash_input).hexdigest()[:6]

    return f"{sanitized}-{hash_hex}.{ext}"


def resolve_collision(base_path: Path, filename: str) -> str:
    """Resolve filename collision by appending counter.

    Args:
        base_path: Directory where file will be stored
        filename: Proposed filename

    Returns:
        Final filename (possibly with -1, -2, etc. appended)
    """
    final_path = base_path / filename

    if not final_path.exists():
        return filename

    # Split into name and extension
    if "." in filename:
        name, ext = filename.rsplit(".", 1)
    else:
        name, ext = filename, ""

    counter = 1
    while final_path.exists():
        if ext:
            new_filename = f"{name}-{counter}.{ext}"
        else:
            new_filename = f"{name}-{counter}"
        final_path = base_path / new_filename
        counter += 1

        # Safety: prevent infinite loop
        if counter > 1000:
            raise RuntimeError("Too many filename collisions")

    return final_path.name


# ---------------------------------------------------------------------------
# Upload Storage
# ---------------------------------------------------------------------------

def store_upload(
    content: bytes,
    filename: str,
    uploads_dir: Path,
    year: str,
    month: str,
) -> tuple[str, Path]:
    """Store uploaded file using temp-file-then-move pattern.

    Args:
        content: File content as bytes
        filename: Original filename
        uploads_dir: Base uploads directory (e.g., teams/self/uploads/)
        year: Year subdirectory (e.g., "2026")
        month: Month subdirectory (e.g., "02")

    Returns:
        Tuple of (final_filename, final_path)

    Raises:
        IOError: If file write fails
    """
    # Ensure .tmp directory exists
    tmp_dir = uploads_dir / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Write to temp file
    tmp_filename = f"{uuid.uuid4()}.tmp"
    tmp_path = tmp_dir / tmp_filename

    try:
        with tmp_path.open("wb") as f:
            f.write(content)

        # Generate final filename
        final_filename = generate_filename(filename)

        # Ensure year/month directory exists
        final_dir = uploads_dir / year / month
        final_dir.mkdir(parents=True, exist_ok=True)

        # Resolve collision
        final_filename = resolve_collision(final_dir, final_filename)
        final_path = final_dir / final_filename

        # Move from tmp to final location
        tmp_path.rename(final_path)

        return final_filename, final_path

    except Exception as e:
        # Clean up temp file on error
        tmp_path.unlink(missing_ok=True)
        raise IOError(f"Failed to store file: {e}") from e


# ---------------------------------------------------------------------------
# Path Validation (for serve endpoint)
# ---------------------------------------------------------------------------

def safe_path(base: Path, user_input: str) -> Path | None:
    """Validate that user-provided path is within base directory.

    Prevents path traversal attacks (e.g., ../../etc/passwd).

    Args:
        base: Base directory (e.g., teams/self/uploads/)
        user_input: User-provided path components

    Returns:
        Resolved path if within base, None otherwise
    """
    # Reject paths containing '..' to prevent traversal attempts
    if ".." in user_input:
        return None

    try:
        full_path = (base / user_input).resolve()
        # Check that resolved path is within base
        full_path.relative_to(base.resolve())
        return full_path
    except (ValueError, RuntimeError):
        return None
