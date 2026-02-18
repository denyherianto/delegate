"""Tests for extract_edit_diff() — diff snippet extraction for Edit/Write tool calls.

Verifies:
- Edit: diff between old_string and new_string from tool input.
- Write: diff between existing file content and new content (or all-adds if file missing).
- Max 3 lines returned.
- Non-edit tools return None.
- Identical content returns None.
- Header lines (--- / +++ / @@) are excluded.
- Lines are correctly classified as + / - / context.
"""

import types
import tempfile
import os

import pytest

from delegate.runtime import extract_edit_diff


def _block(name: str, **kwargs) -> object:
    """Build a minimal tool-call block."""
    b = types.SimpleNamespace()
    b.name = name
    b.input = kwargs
    return b


# ---------------------------------------------------------------------------
# Edit tool
# ---------------------------------------------------------------------------


class TestExtractEditDiffEdit:
    def test_simple_replacement(self):
        block = _block("Edit", old_string="foo\n", new_string="bar\n")
        result = extract_edit_diff(block)
        assert result is not None
        assert any(line.startswith("-") for line in result)
        assert any(line.startswith("+") for line in result)

    def test_returns_at_most_3_lines(self):
        old = "line1\nline2\nline3\nline4\n"
        new = "CHANGED1\nCHANGED2\nCHANGED3\nCHANGED4\n"
        block = _block("Edit", old_string=old, new_string=new)
        result = extract_edit_diff(block)
        assert result is not None
        assert len(result) <= 3

    def test_identical_content_returns_none(self):
        block = _block("Edit", old_string="same\n", new_string="same\n")
        result = extract_edit_diff(block)
        assert result is None

    def test_no_header_lines_in_output(self):
        block = _block("Edit", old_string="a\n", new_string="b\n")
        result = extract_edit_diff(block)
        assert result is not None
        for line in result:
            assert not line.startswith("---")
            assert not line.startswith("+++")
            assert not line.startswith("@@")

    def test_added_lines_start_with_plus(self):
        block = _block("Edit", old_string="", new_string="new line\n")
        result = extract_edit_diff(block)
        assert result is not None
        assert all(line.startswith("+") for line in result)

    def test_removed_lines_start_with_minus(self):
        block = _block("Edit", old_string="old line\n", new_string="")
        result = extract_edit_diff(block)
        assert result is not None
        assert all(line.startswith("-") for line in result)

    def test_context_lines_have_space_prefix(self):
        # Context lines appear when surrounding lines are unchanged
        old = "ctx\nchange me\nctx2\n"
        new = "ctx\nchanged\nctx2\n"
        block = _block("Edit", old_string=old, new_string=new)
        result = extract_edit_diff(block)
        assert result is not None
        # At least some lines: may include context, +, -
        for line in result:
            assert line[0] in ("+", "-", " "), f"Unexpected prefix in: {line!r}"

    def test_empty_old_string(self):
        block = _block("Edit", old_string="", new_string="hello\n")
        result = extract_edit_diff(block)
        assert result is not None

    def test_missing_input_fields(self):
        # No old_string/new_string — treated as empty strings, should return None (no diff)
        block = _block("Edit")
        result = extract_edit_diff(block)
        assert result is None

    def test_no_trailing_newlines_in_output(self):
        block = _block("Edit", old_string="a\n", new_string="b\n")
        result = extract_edit_diff(block)
        assert result is not None
        for line in result:
            assert not line.endswith("\n")
            assert not line.endswith("\r")


# ---------------------------------------------------------------------------
# Write tool
# ---------------------------------------------------------------------------


class TestExtractEditDiffWrite:
    def test_new_file_all_additions(self):
        # file_path points to a non-existent file → old content is empty
        block = _block("Write", file_path="/nonexistent/path/xyz.txt", content="hello\n")
        result = extract_edit_diff(block)
        assert result is not None
        assert all(line.startswith("+") for line in result)

    def test_existing_file_shows_diff(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("original content\n")
            fname = f.name
        try:
            block = _block("Write", file_path=fname, content="new content\n")
            result = extract_edit_diff(block)
            assert result is not None
            assert any(line.startswith("-") for line in result)
            assert any(line.startswith("+") for line in result)
        finally:
            os.unlink(fname)

    def test_identical_content_returns_none(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("same\n")
            fname = f.name
        try:
            block = _block("Write", file_path=fname, content="same\n")
            result = extract_edit_diff(block)
            assert result is None
        finally:
            os.unlink(fname)

    def test_returns_at_most_3_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("a\nb\nc\nd\n")
            fname = f.name
        try:
            block = _block("Write", file_path=fname, content="W\nX\nY\nZ\n")
            result = extract_edit_diff(block)
            assert result is not None
            assert len(result) <= 3
        finally:
            os.unlink(fname)


# ---------------------------------------------------------------------------
# Non-edit tools
# ---------------------------------------------------------------------------


class TestExtractEditDiffNonEditTools:
    def test_bash_returns_none(self):
        block = _block("Bash", command="ls -la")
        assert extract_edit_diff(block) is None

    def test_read_returns_none(self):
        block = _block("Read", file_path="/some/file.txt")
        assert extract_edit_diff(block) is None

    def test_grep_returns_none(self):
        block = _block("Grep", pattern="foo")
        assert extract_edit_diff(block) is None

    def test_no_name_attr_returns_none(self):
        block = types.SimpleNamespace(input={})
        assert extract_edit_diff(block) is None

    def test_task_create_returns_none(self):
        block = _block("mcp__delegate__task_create", title="test")
        assert extract_edit_diff(block) is None
