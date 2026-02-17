"""Tests for delegate.prompt.Prompt — parity with agent.py functions.

The Prompt class was extracted from agent.py's ``build_system_prompt()``,
``build_user_message()``, and ``build_reflection_message()``.  These
tests verify byte-identical output between the old and new code paths.
"""

from __future__ import annotations

import pytest

from delegate.agent import build_system_prompt, build_user_message, build_reflection_message
from delegate.prompt import Prompt
from delegate.mailbox import Message


# Use the standard conftest fixtures (tmp_team, SAMPLE_*)
from tests.conftest import (
    SAMPLE_TEAM_NAME,
    SAMPLE_MANAGER,
    SAMPLE_WORKERS,
    SAMPLE_HUMAN,
)


class TestPromptParity:
    """Verify that Prompt methods produce identical output to agent.py functions."""

    def test_preamble_matches_system_prompt(self, tmp_team):
        """Prompt.build_preamble() == agent.build_system_prompt() for each agent."""
        for agent in [SAMPLE_MANAGER] + list(SAMPLE_WORKERS):
            old = build_system_prompt(tmp_team, SAMPLE_TEAM_NAME, agent)
            new = Prompt(tmp_team, SAMPLE_TEAM_NAME, agent).build_preamble()
            assert old == new, (
                f"Preamble mismatch for {agent}:\n"
                f"--- OLD (first 500 chars) ---\n{old[:500]}\n"
                f"--- NEW (first 500 chars) ---\n{new[:500]}"
            )

    def test_user_message_no_messages(self, tmp_team):
        """build_user_message() with empty inbox matches for each agent."""
        for agent in [SAMPLE_MANAGER] + list(SAMPLE_WORKERS):
            old = build_user_message(
                tmp_team, SAMPLE_TEAM_NAME, agent,
                messages=[],
            )
            new = Prompt(tmp_team, SAMPLE_TEAM_NAME, agent).build_user_message(
                messages=[],
            )
            assert old == new, (
                f"User message (no msgs) mismatch for {agent}:\n"
                f"--- OLD ---\n{old}\n--- NEW ---\n{new}"
            )

    def test_user_message_with_messages(self, tmp_team):
        """build_user_message() with inbox messages matches."""
        msgs = [
            Message(
                sender=SAMPLE_HUMAN,
                recipient=SAMPLE_WORKERS[0],
                time="2026-02-15T10:00:00Z",
                body="Hello Alice, please start working on the API.",
                task_id=None,
            ),
        ]
        old = build_user_message(
            tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0],
            messages=msgs,
        )
        new = Prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0]).build_user_message(
            messages=msgs,
        )
        assert old == new, (
            f"User message (with msgs) mismatch:\n"
            f"--- OLD ---\n{old}\n--- NEW ---\n{new}"
        )

    def test_user_message_with_task(self, tmp_team):
        """build_user_message() with a task context matches."""
        from delegate.task import create_task
        task = create_task(
            tmp_team, SAMPLE_TEAM_NAME,
            title="Build REST API",
            assignee=SAMPLE_WORKERS[0],
            description="Create the /api/v1 endpoints",
            priority="high",
        )
        msgs = [
            Message(
                sender=SAMPLE_MANAGER,
                recipient=SAMPLE_WORKERS[0],
                time="2026-02-15T10:00:00Z",
                body="Start working on this task.",
                task_id=task["id"],
            ),
        ]
        old = build_user_message(
            tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0],
            messages=msgs,
            current_task=task,
        )
        new = Prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0]).build_user_message(
            messages=msgs,
            current_task=task,
        )
        assert old == new, (
            f"User message (with task) mismatch:\n"
            f"--- OLD (first 1000) ---\n{old[:1000]}\n--- NEW (first 1000) ---\n{new[:1000]}"
        )

    def test_reflection_message_matches(self, tmp_team):
        """build_reflection_message() matches for each agent."""
        for agent in [SAMPLE_MANAGER] + list(SAMPLE_WORKERS):
            old = build_reflection_message(tmp_team, SAMPLE_TEAM_NAME, agent)
            new = Prompt(tmp_team, SAMPLE_TEAM_NAME, agent).build_reflection_message()
            assert old == new, (
                f"Reflection mismatch for {agent}:\n"
                f"--- OLD ---\n{old}\n--- NEW ---\n{new}"
            )

    def test_preamble_with_reflections(self, tmp_team):
        """Preamble includes reflections when reflections.md exists."""
        from delegate.paths import agent_dir
        ad = agent_dir(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0])
        notes_dir = ad / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        (notes_dir / "reflections.md").write_text(
            "- Always run tests before marking in_review\n"
            "- Check imports after refactoring\n"
        )

        old = build_system_prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0])
        new = Prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0]).build_preamble()
        assert old == new
        assert "Always run tests" in new

    def test_preamble_with_override_charter(self, tmp_team):
        """Preamble includes team override charter when override.md exists."""
        from delegate.paths import team_dir as _team_dir
        team_dir = _team_dir(tmp_team, SAMPLE_TEAM_NAME)
        (team_dir / "override.md").write_text(
            "# Custom Rules\n\nAll code must have 90% test coverage.\n"
        )

        old = build_system_prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0])
        new = Prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0]).build_preamble()
        assert old == new
        assert "90% test coverage" in new


class TestPromptUnit:
    """Unit tests for individual Prompt methods."""

    def test_section_context_md_empty(self, tmp_team):
        """No context.md → empty string."""
        p = Prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0])
        assert p._section_context_md() == ""

    def test_section_context_md_present(self, tmp_team):
        """context.md content is included."""
        from delegate.paths import agent_dir
        ad = agent_dir(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0])
        (ad / "context.md").write_text("Last session: 2026-02-15T10:00:00Z\nTurns: 3\n")

        p = Prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0])
        result = p._section_context_md()
        assert "PREVIOUS SESSION CONTEXT" in result
        assert "Turns: 3" in result

    def test_section_task_context_none(self, tmp_team):
        """No task → empty string."""
        p = Prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0])
        assert p._section_task_context(None) == ""

    def test_section_task_context_basic(self, tmp_team):
        """Task context includes title, status, description."""
        p = Prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0])
        task = {
            "id": 42,
            "title": "Build REST API",
            "status": "in_progress",
            "description": "Create endpoints",
        }
        result = p._section_task_context(task)
        assert "T0042" in result
        assert "Build REST API" in result
        assert "in_progress" in result
        assert "Create endpoints" in result

    def test_section_other_tasks_empty(self, tmp_team):
        """No other tasks → empty string."""
        p = Prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0])
        assert p._section_other_tasks(None) == ""


class TestInstructionFiles:
    """Tests for collect_instruction_files() and repo instruction injection."""

    def test_collect_instruction_files_empty(self, tmp_path):
        """No instruction files in repo -> returns empty string."""
        from delegate.prompt import collect_instruction_files
        assert collect_instruction_files(tmp_path) == ""

    def test_collect_instruction_files_claude_md(self, tmp_path):
        """CLAUDE.md in root is collected."""
        from delegate.prompt import collect_instruction_files
        (tmp_path / "CLAUDE.md").write_text("Use snake_case for all identifiers.")
        result = collect_instruction_files(tmp_path)
        assert "Use snake_case" in result
        assert "CLAUDE.md" in result

    def test_collect_instruction_files_case_insensitive(self, tmp_path):
        """Lowercase claude.md still matches the CLAUDE.md candidate."""
        from delegate.prompt import collect_instruction_files
        (tmp_path / "claude.md").write_text("Lowercase instructions here.")
        result = collect_instruction_files(tmp_path)
        assert "Lowercase instructions here." in result

    def test_collect_instruction_files_multiple(self, tmp_path):
        """CLAUDE.md and .cursorrules are both collected, separated by ---."""
        from delegate.prompt import collect_instruction_files
        (tmp_path / "CLAUDE.md").write_text("Claude-specific rules.")
        (tmp_path / ".cursorrules").write_text("Cursor-specific rules.")
        result = collect_instruction_files(tmp_path)
        assert "Claude-specific rules." in result
        assert "Cursor-specific rules." in result
        assert "---" in result

    def test_collect_instruction_files_subdirectory(self, tmp_path):
        """.claude/instructions.md in subdirectory is collected."""
        from delegate.prompt import collect_instruction_files
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "instructions.md").write_text("Subdirectory instructions.")
        result = collect_instruction_files(tmp_path)
        assert "Subdirectory instructions." in result
        assert ".claude/instructions.md" in result

    def test_preamble_includes_repo_instructions(self, tmp_team, tmp_path):
        """Preamble includes content from repo instruction files."""
        import os
        from delegate.repo import register_repo

        # Create a fake git repo with a CLAUDE.md
        fake_repo = tmp_path / "myrepo"
        fake_repo.mkdir()
        (fake_repo / ".git").mkdir()
        (fake_repo / "CLAUDE.md").write_text("Always write docstrings.")

        register_repo(tmp_team, SAMPLE_TEAM_NAME, str(fake_repo), name="myrepo")

        old = build_system_prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0])
        new = Prompt(tmp_team, SAMPLE_TEAM_NAME, SAMPLE_WORKERS[0]).build_preamble()

        # Both paths should produce identical output
        assert old == new
        # Both should include the repo instruction content
        assert "Always write docstrings." in new
        assert "REPO INSTRUCTIONS" in new
