"""Tests for MCP tool activity summary formatters.

Verifies that _extract_tool_summary() produces human-readable one-liners
for all 13 MCP tools, with correct truncation, optional params, and
graceful fallback on malformed input.
"""

import types

import pytest

from delegate.runtime import _extract_tool_summary, MCP_TOOL_FORMATTERS


def _block(name: str, **kwargs) -> object:
    """Build a minimal tool-call block with the given name and input fields."""
    b = types.SimpleNamespace()
    b.name = name
    b.input = kwargs
    return b


# ---------------------------------------------------------------------------
# Task management tools
# ---------------------------------------------------------------------------


class TestTaskCreate:
    def test_basic(self):
        tool, detail = _extract_tool_summary(
            _block("task_create", title="Fix the bug", priority="high")
        )
        assert tool == "task_create"
        assert detail == 'Created task: "Fix the bug" (high)'

    def test_title_truncated_to_40_chars(self):
        long_title = "A" * 50
        _, detail = _extract_tool_summary(
            _block("task_create", title=long_title, priority="medium")
        )
        assert detail == f'Created task: "{"A" * 40}" (medium)'

    def test_priority_defaults_to_medium_when_missing(self):
        _, detail = _extract_tool_summary(_block("task_create", title="No priority"))
        assert "(medium)" in detail

    def test_empty_title(self):
        _, detail = _extract_tool_summary(_block("task_create", title="", priority="low"))
        assert detail == 'Created task: "" (low)'


class TestTaskAssign:
    def test_basic(self):
        tool, detail = _extract_tool_summary(
            _block("task_assign", task_id=15, assignee="cubic")
        )
        assert tool == "task_assign"
        assert detail == "Assigned T0015 to cubic"

    def test_task_id_zero_padded(self):
        _, detail = _extract_tool_summary(_block("task_assign", task_id=3, assignee="blend"))
        assert detail == "Assigned T0003 to blend"

    def test_missing_params_fallback(self):
        _, detail = _extract_tool_summary(_block("task_assign"))
        assert detail == "Assigned T0000 to ?"


class TestTaskStatus:
    def test_basic(self):
        tool, detail = _extract_tool_summary(
            _block("task_status", task_id=15, new_status="in_review")
        )
        assert tool == "task_status"
        assert detail == "T0015 \u2192 in_review"

    def test_arrow_unicode(self):
        _, detail = _extract_tool_summary(
            _block("task_status", task_id=1, new_status="done")
        )
        assert "\u2192" in detail

    def test_missing_params_fallback(self):
        _, detail = _extract_tool_summary(_block("task_status"))
        assert detail == "T0000 \u2192 ?"


class TestTaskComment:
    def test_basic(self):
        tool, detail = _extract_tool_summary(
            _block("task_comment", task_id=22, body="Some long comment text")
        )
        assert tool == "task_comment"
        assert detail == "Commented on T0022"

    def test_body_not_included_in_detail(self):
        _, detail = _extract_tool_summary(
            _block("task_comment", task_id=5, body="Very long comment that should not appear")
        )
        assert "long comment" not in detail


class TestTaskShow:
    def test_basic(self):
        tool, detail = _extract_tool_summary(_block("task_show", task_id=7))
        assert tool == "task_show"
        assert detail == "Viewed T0007"


class TestTaskList:
    def test_basic(self):
        tool, detail = _extract_tool_summary(
            _block("task_list", status="in_progress", assignee="blend")
        )
        assert tool == "task_list"
        assert detail == "Listed tasks"

    def test_no_params(self):
        _, detail = _extract_tool_summary(_block("task_list"))
        assert detail == "Listed tasks"

    def test_filter_params_not_shown(self):
        _, detail = _extract_tool_summary(
            _block("task_list", status="done", assignee="cubic")
        )
        assert "done" not in detail
        assert "cubic" not in detail


class TestTaskCancel:
    def test_basic(self):
        tool, detail = _extract_tool_summary(_block("task_cancel", task_id=19))
        assert tool == "task_cancel"
        assert detail == "Cancelled T0019"


class TestTaskAttach:
    def test_basic(self):
        tool, detail = _extract_tool_summary(
            _block("task_attach", task_id=15, file_path="/some/deep/path/spec.md")
        )
        assert tool == "task_attach"
        assert detail == "Attached spec.md to T0015"

    def test_basename_extracted(self):
        _, detail = _extract_tool_summary(
            _block("task_attach", task_id=1, file_path="/Users/nikhil/teams/shared/design.png")
        )
        assert "design.png" in detail
        assert "/Users" not in detail

    def test_missing_file_path(self):
        _, detail = _extract_tool_summary(_block("task_attach", task_id=1))
        assert "?" in detail


class TestTaskDetach:
    def test_basic(self):
        tool, detail = _extract_tool_summary(
            _block("task_detach", task_id=15, file_path="/some/path/old-spec.md")
        )
        assert tool == "task_detach"
        assert detail == "Detached old-spec.md from T0015"

    def test_basename_extracted(self):
        _, detail = _extract_tool_summary(
            _block("task_detach", task_id=3, file_path="/deep/nested/file.txt")
        )
        assert "file.txt" in detail
        assert "/deep" not in detail


# ---------------------------------------------------------------------------
# Communication tools
# ---------------------------------------------------------------------------


class TestMailboxSend:
    def test_with_task_id(self):
        tool, detail = _extract_tool_summary(
            _block("mailbox_send", recipient="cubic", message="Hello", task_id=15)
        )
        assert tool == "mailbox_send"
        assert detail == "Sent message to cubic (re: T0015)"

    def test_without_task_id(self):
        _, detail = _extract_tool_summary(
            _block("mailbox_send", recipient="nikhil", message="Hello")
        )
        assert detail == "Sent message to nikhil"
        assert "re:" not in detail

    def test_task_id_none_omitted(self):
        _, detail = _extract_tool_summary(
            _block("mailbox_send", recipient="blend", message="Hi", task_id=None)
        )
        assert "re:" not in detail

    def test_missing_recipient(self):
        _, detail = _extract_tool_summary(_block("mailbox_send", message="Hi"))
        assert detail == "Sent message to ?"


class TestMailboxInbox:
    def test_basic(self):
        tool, detail = _extract_tool_summary(_block("mailbox_inbox"))
        assert tool == "mailbox_inbox"
        assert detail == "Checked inbox"

    def test_no_params_needed(self):
        # inbox takes no params — verify it works with an empty input dict
        _, detail = _extract_tool_summary(_block("mailbox_inbox"))
        assert detail == "Checked inbox"


# ---------------------------------------------------------------------------
# Repository tools
# ---------------------------------------------------------------------------


class TestRepoList:
    def test_basic(self):
        tool, detail = _extract_tool_summary(_block("repo_list"))
        assert tool == "repo_list"
        assert detail == "Listed repos"


class TestRebaseToMain:
    def test_basic(self):
        tool, detail = _extract_tool_summary(_block("rebase_to_main", task_id=16))
        assert tool == "rebase_to_main"
        assert detail == "Rebasing T0016 onto main"

    def test_missing_task_id(self):
        _, detail = _extract_tool_summary(_block("rebase_to_main"))
        assert detail == "Rebasing T0000 onto main"


# ---------------------------------------------------------------------------
# Formatter dict completeness
# ---------------------------------------------------------------------------


class TestFormatterCompleteness:
    EXPECTED_TOOLS = {
        # Task management (9)
        "task_create", "task_assign", "task_status", "task_comment",
        "task_show", "task_list", "task_cancel", "task_attach", "task_detach",
        # Communication (2)
        "mailbox_send", "mailbox_inbox",
        # Repository (2)
        "repo_list", "rebase_to_main",
    }

    def test_all_13_tools_covered(self):
        assert set(MCP_TOOL_FORMATTERS.keys()) == self.EXPECTED_TOOLS

    def test_count_is_13(self):
        assert len(MCP_TOOL_FORMATTERS) == 13


# ---------------------------------------------------------------------------
# Error fallback
# ---------------------------------------------------------------------------


class TestFormatterFallback:
    def test_malformed_input_falls_back_gracefully(self, monkeypatch):
        """If a formatter raises, _extract_tool_summary falls back to key list."""

        def bad_formatter(inp):
            raise ValueError("formatter exploded")

        monkeypatch.setitem(MCP_TOOL_FORMATTERS, "task_create", bad_formatter)

        tool, detail = _extract_tool_summary(
            _block("task_create", title="Hello", priority="high")
        )
        assert tool == "task_create"
        # Fallback: key names listed (sorted, up to 3)
        assert "task_create" in detail or "priority" in detail or "title" in detail

    def test_unknown_tool_uses_legacy_fallback(self):
        """Tools not in MCP_TOOL_FORMATTERS still get key-list formatting."""
        tool, detail = _extract_tool_summary(
            _block("some_future_tool", foo="bar", baz="qux")
        )
        assert tool == "some_future_tool"
        assert "some_future_tool" in detail

    def test_non_tool_block_returns_empty(self):
        """Blocks without a .name attribute return empty strings."""
        block = types.SimpleNamespace()  # no .name
        assert _extract_tool_summary(block) == ("", "")

    def test_built_in_tools_unchanged(self):
        """Existing built-in formatters are not affected by MCP changes."""
        tool, detail = _extract_tool_summary(
            _block("Bash", command="echo hello world")
        )
        assert tool == "Bash"
        assert detail == "echo hello world"

        tool, detail = _extract_tool_summary(
            _block("Read", file_path="/some/file.py")
        )
        assert tool == "Read"
        assert detail == "/some/file.py"

        tool, detail = _extract_tool_summary(
            _block("Grep", pattern="def foo")
        )
        assert tool == "Grep"
        assert detail == "def foo"
