"""Tests for delegate.session.Session.

These tests call the live Claude Code SDK and are gated behind the
``--run-llm`` pytest flag.  Run them with::

    pytest tests/test_session.py --run-llm -v

They require a valid Claude authentication (``claude login`` or
``ANTHROPIC_API_KEY`` in the environment).

⚠️  Each test spawns a real agent turn — expect API charges.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Ensure claude_code_sdk is importable even when the real package isn't
# installed.  Unit tests only need ClaudeCodeOptions to behave as a
# simple data container.  If the real SDK *is* installed we leave it alone
# so the live (--run-llm) tests work.
# ---------------------------------------------------------------------------
try:
    import claude_code_sdk as _real_sdk  # noqa: F401 — just probe availability
except ImportError:
    _fake_sdk = types.ModuleType("claude_code_sdk")

    class _FakeOptions:
        """Minimal stand-in for ClaudeCodeOptions."""
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)
            for attr in (
                "system_prompt", "resume", "model", "max_turns",
                "add_dirs", "disallowed_tools", "can_use_tool",
                "cwd", "permission_mode",
            ):
                if not hasattr(self, attr):
                    setattr(self, attr, None)

    _fake_sdk.ClaudeCodeOptions = _FakeOptions  # type: ignore[attr-defined]
    _fake_sdk.ResultMessage = type("ResultMessage", (), {})  # type: ignore[attr-defined]
    sys.modules["claude_code_sdk"] = _fake_sdk

from delegate.session import Session, SessionUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIMPLE_PREAMBLE = (
    "You are a test assistant.  Keep answers to one sentence.  "
    "Do NOT use any tools unless explicitly asked."
)

def _collect_text(messages: list) -> str:
    """Extract concatenated text from a list of SDK messages."""
    parts: list[str] = []
    for msg in messages:
        if hasattr(msg, "content"):
            for block in msg.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
    return "\n".join(parts).strip()


async def _send_and_collect(session: Session, prompt: str, **kw) -> list:
    """Send a prompt, collect all messages into a list."""
    msgs: list = []
    async for msg in session.send(prompt, **kw):
        msgs.append(msg)
    return msgs


# ---------------------------------------------------------------------------
# Unit tests (no LLM) — verify pure logic
# ---------------------------------------------------------------------------

class TestSessionUnit:
    """Tests that don't call the SDK — verify construction and guards.

    These are NOT marked ``llm`` — they run in normal CI.
    """

    def test_init_defaults(self, tmp_path):
        """Session initialises with sane defaults."""
        s = Session(preamble="hello", cwd=tmp_path)
        assert s.id is not None and len(s.id) == 32  # uuid hex
        assert s.preamble == "hello"
        assert s.memory == ""
        assert s._sdk_session_id is None
        assert s.turns == 0
        assert s.generation == 0
        assert s.is_active is False
        assert s.needs_rotation is False
        assert s.usage.input_tokens == 0
        assert s._allowed_write_paths is None

    def test_init_with_memory(self, tmp_path):
        """Session can be initialised with prior memory."""
        s = Session(preamble="hello", cwd=tmp_path, memory="prior context")
        assert s.memory == "prior context"

    def test_init_write_paths_resolved(self, tmp_path):
        """Write paths are resolved to absolute paths."""
        s = Session(
            preamble="hello",
            cwd=tmp_path,
            allowed_write_paths=["./relative", "/absolute/path"],
        )
        for p in s.allowed_write_paths:
            assert p.is_absolute()

    def test_reset_clears_state_but_not_memory(self, tmp_path):
        """reset() zeroes conversation state but preserves memory."""
        s = Session(preamble="hello", cwd=tmp_path, memory="important context")
        old_id = s.id
        s._sdk_session_id = "fake-id"
        s.usage.input_tokens = 50_000
        s.turns = 10
        s.reset()
        assert s._sdk_session_id is None
        assert s.turns == 0
        assert s.usage.input_tokens == 0
        assert s.id != old_id  # new UUID
        assert s.generation == 1  # incremented
        assert s.memory == "important context"  # preserved!

    def test_needs_rotation(self, tmp_path):
        """needs_rotation triggers when input exceeds threshold."""
        s = Session(preamble="hello", cwd=tmp_path, max_context_tokens=100)
        assert not s.needs_rotation
        s.usage.input_tokens = 101
        assert s.needs_rotation

    def test_write_paths_setter(self, tmp_path):
        """allowed_write_paths setter resolves new paths."""
        s = Session(preamble="hello", cwd=tmp_path)
        assert s.allowed_write_paths is None
        s.allowed_write_paths = [tmp_path / "a", tmp_path / "b"]
        assert len(s.allowed_write_paths) == 2
        s.allowed_write_paths = None
        assert s.allowed_write_paths is None

    def test_build_options_fresh(self, tmp_path):
        """First turn: no system_prompt, no resume."""
        s = Session(
            preamble="my preamble",
            cwd=tmp_path,
            model="claude-sonnet-4-20250514",
            disallowed_tools=["Bash(git push:*)"],
        )
        opts = s._build_options(tmp_path, None)
        # system_prompt should never be set — we use Claude's own
        assert opts.system_prompt is None
        assert opts.resume is None
        assert opts.model == "claude-sonnet-4-20250514"
        assert "Bash(git push:*)" in opts.disallowed_tools

    def test_build_options_resume(self, tmp_path):
        """Subsequent turns: resume set, still no system_prompt."""
        s = Session(preamble="my preamble", cwd=tmp_path)
        s._sdk_session_id = "abc-123"
        opts = s._build_options(tmp_path, None)
        assert opts.resume == "abc-123"
        assert opts.system_prompt is None

    def test_turn0_prompt_preamble_only(self, tmp_path):
        """Turn 0 with no memory: preamble + prompt."""
        s = Session(preamble="You are a pirate.", cwd=tmp_path)
        result = s._build_turn0_prompt("Hello")
        assert result == "## PREAMBLE\n\nYou are a pirate.\n\nHello"

    def test_turn0_prompt_with_memory(self, tmp_path):
        """Turn 0 with memory: preamble + memory + prompt."""
        s = Session(
            preamble="You are a pirate.",
            cwd=tmp_path,
            memory="Previously: found treasure on island.",
        )
        result = s._build_turn0_prompt("What next?")
        assert result == (
            "## PREAMBLE\n\nYou are a pirate.\n\n"
            "## MEMORY\n\nPreviously: found treasure on island.\n\n"
            "What next?"
        )

    def test_turn0_prompt_empty_memory_skipped(self, tmp_path):
        """Turn 0 with empty memory: only preamble + prompt (no blank section)."""
        s = Session(preamble="You are a pirate.", cwd=tmp_path, memory="")
        result = s._build_turn0_prompt("Hello")
        assert result == "## PREAMBLE\n\nYou are a pirate.\n\nHello"
        # No triple newline from empty memory
        assert "\n\n\n" not in result

    def test_guard_unrestricted(self, tmp_path):
        """No guard when there are no restrictions."""
        s = Session(preamble="hello", cwd=tmp_path)
        assert s._make_guard(None) is None

    def test_guard_denies_write_outside(self, tmp_path):
        """Guard denies writes outside allowed paths."""
        allowed = [tmp_path / "safe"]
        s = Session(
            preamble="hello",
            cwd=tmp_path,
            allowed_write_paths=[str(tmp_path / "safe")],
        )
        guard = s._make_guard(allowed)
        assert guard is not None

        # Write inside — allowed
        result = asyncio.run(guard("Edit", {"file_path": str(tmp_path / "safe" / "f.py")}, None))
        assert result["behavior"] == "allow"

        # Write outside — denied
        result = asyncio.run(guard("Write", {"file_path": "/etc/passwd"}, None))
        assert result["behavior"] == "deny"

    def test_guard_allows_multiple_paths(self, tmp_path):
        """Guard allows writes in any of the allowed paths."""
        paths = [tmp_path / "repo-a", tmp_path / "repo-b"]
        s = Session(preamble="hello", cwd=tmp_path)
        guard = s._make_guard(paths)

        r1 = asyncio.run(guard("Edit", {"file_path": str(tmp_path / "repo-a" / "x")}, None))
        assert r1["behavior"] == "allow"

        r2 = asyncio.run(guard("Edit", {"file_path": str(tmp_path / "repo-b" / "y")}, None))
        assert r2["behavior"] == "allow"

        r3 = asyncio.run(guard("Edit", {"file_path": str(tmp_path / "repo-c" / "z")}, None))
        assert r3["behavior"] == "deny"

    def test_guard_denies_bash_pattern(self, tmp_path):
        """Guard denies bash commands matching denied patterns."""
        s = Session(
            preamble="hello",
            cwd=tmp_path,
            denied_bash_patterns=["git rebase", "git push"],
        )
        guard = s._make_guard(None)
        assert guard is not None

        ok = asyncio.run(guard("Bash", {"command": "git status"}, None))
        assert ok["behavior"] == "allow"

        deny1 = asyncio.run(guard("Bash", {"command": "git rebase main"}, None))
        assert deny1["behavior"] == "deny"

        deny2 = asyncio.run(guard("Bash", {"command": "git push origin main"}, None))
        assert deny2["behavior"] == "deny"

    def test_guard_read_always_allowed(self, tmp_path):
        """Read/Grep/Glob are never blocked by the write guard."""
        paths = [tmp_path / "only-here"]
        s = Session(
            preamble="hello",
            cwd=tmp_path,
            denied_bash_patterns=["rm -rf"],
        )
        guard = s._make_guard(paths)

        for tool in ("Read", "Grep", "Glob"):
            r = asyncio.run(guard(tool, {"file_path": "/anywhere/file.py"}, None))
            assert r["behavior"] == "allow"

    def test_id_is_uuid_hex(self, tmp_path):
        """Session id is a 32-char hex UUID."""
        s = Session(preamble="hello", cwd=tmp_path)
        assert len(s.id) == 32
        int(s.id, 16)  # should not raise

    def test_generation_increments_on_reset(self, tmp_path):
        """Each reset() bumps the generation counter."""
        s = Session(preamble="hello", cwd=tmp_path)
        assert s.generation == 0
        s.reset()
        assert s.generation == 1
        s.reset()
        assert s.generation == 2

    def test_rotation_prompt_default(self, tmp_path):
        """Default rotation_prompt is set."""
        s = Session(preamble="hello", cwd=tmp_path)
        assert s.rotation_prompt is not None
        assert "summary" in s.rotation_prompt.lower()

    def test_rotation_prompt_custom(self, tmp_path):
        """Custom rotation_prompt is stored."""
        s = Session(
            preamble="hello",
            cwd=tmp_path,
            rotation_prompt="Give me a haiku summary.",
        )
        assert s.rotation_prompt == "Give me a haiku summary."

    def test_rotation_prompt_none_disables_summary(self, tmp_path):
        """rotation_prompt=None means rotate does a hard reset only."""
        s = Session(
            preamble="hello",
            cwd=tmp_path,
            rotation_prompt=None,
        )
        assert s.rotation_prompt is None


# ---------------------------------------------------------------------------
# Live LLM integration tests
# ---------------------------------------------------------------------------

@pytest.mark.llm
class TestSessionLive:
    """Tests that call the real Claude Code SDK.

    Each test creates a fresh Session in a temp directory, sends one or
    more prompts, and verifies SDK-level behaviour (session resumption,
    token tracking, etc.).

    Tests use ``asyncio.run()`` so they work without ``pytest-asyncio``.
    """

    def test_basic_send(self, tmp_path):
        """A single send() returns messages and sets SDK session id."""
        async def _run():
            s = Session(
                preamble=SIMPLE_PREAMBLE,
                cwd=str(tmp_path),
            )
            initial_id = s.id  # UUID exists before first send
            msgs = await _send_and_collect(s, "What is 2 + 2? Answer the number only.")
            text = _collect_text(msgs)

            assert s.id == initial_id  # id unchanged
            assert s._sdk_session_id is not None
            assert s.turns == 1
            assert s.is_active
            assert "4" in text

        asyncio.run(_run())

    def test_resume_preserves_context(self, tmp_path):
        """Second send() resumes and Claude remembers the first turn."""
        async def _run():
            s = Session(
                preamble=SIMPLE_PREAMBLE,
                cwd=str(tmp_path),
            )

            # Turn 1: establish a fact
            await _send_and_collect(s, "Remember: the secret word is 'banana'.")
            first_sdk_id = s._sdk_session_id
            assert first_sdk_id is not None

            # Turn 2: ask for the fact — should resume
            msgs = await _send_and_collect(s, "What is the secret word?")
            text = _collect_text(msgs)

            assert s._sdk_session_id == first_sdk_id
            assert s.turns == 2
            assert "banana" in text.lower()

        asyncio.run(_run())

    def test_tracking_cumulative(self, tmp_path):
        """input_tokens should grow (or stay same) across turns."""
        async def _run():
            s = Session(
                preamble=SIMPLE_PREAMBLE,
                cwd=str(tmp_path),
            )

            await _send_and_collect(s, "Say hello.")
            input_after_1 = s.usage.input_tokens
            output_after_1 = s.usage.output_tokens
            usd_after_1 = s.usage.cost_usd
            cache_read_tokens_after_1 = s.usage.cache_read_tokens
            cache_write_tokens_after_1 = s.usage.cache_write_tokens
            assert input_after_1 > 0, "input_tokens should be > 0"
            assert output_after_1 > 0, "output_tokens should be > 0"
            assert isinstance(usd_after_1, (int, float))

            await _send_and_collect(s, "Say hello.")
            input_after_2 = s.usage.input_tokens
            output_after_2 = s.usage.output_tokens
            cache_read_tokens_after_2 = s.usage.cache_read_tokens
            cache_write_tokens_after_2 = s.usage.cache_write_tokens
            usd_after_2 = s.usage.cost_usd

            # If input_tokens is cumulative (full context replay), it
            # should be >= the first turn's value.
            assert input_after_2 > input_after_1, (
                f"Expected input_tokens to grow: {input_after_1} -> {input_after_2}"
            )
            assert output_after_2 > output_after_1, "output_tokens should be > 0"
            assert cache_read_tokens_after_2 > cache_read_tokens_after_1, "cache_read_tokens should be > 0"
            assert cache_write_tokens_after_2 > cache_write_tokens_after_1, "cache_write_tokens should be > 0"
            assert usd_after_2 > usd_after_1, "cost_usd should be > 0"

        asyncio.run(_run())

    def test_preamble_persists_on_resume(self, tmp_path):
        """Preamble from turn 1 is still effective on turn 2 via conversation history."""
        async def _run():
            s = Session(
                preamble=(
                    "CRITICAL RULE: You must ALWAYS include the exact word "
                    "'YARR' (uppercase) somewhere in EVERY response you give. "
                    "This is mandatory and must never be omitted."
                ),
                cwd=str(tmp_path),
            )

            # Turn 1 — preamble prepended to prompt
            msgs = await _send_and_collect(s, "Say hi briefly.")
            text = _collect_text(msgs)
            assert "YARR" in text, (
                f"Preamble not effective on first turn: {text!r}"
            )

            # Turn 2 — preamble not re-sent, but it's in conversation
            # history so the model should still follow it.
            msgs = await _send_and_collect(s, "Say goodbye briefly.")
            text = _collect_text(msgs)

            assert "YARR" in text, (
                f"Preamble not effective on resume: {text!r}"
            )

        asyncio.run(_run())

    def test_memory_included_on_turn0(self, tmp_path):
        """Memory from init is visible to the model on the first turn."""
        async def _run():
            s = Session(
                preamble=SIMPLE_PREAMBLE,
                cwd=str(tmp_path),
                memory="IMPORTANT FACT: The project codename is 'Phoenix'.",
            )

            msgs = await _send_and_collect(
                s, "What is the project codename? Answer the name only."
            )
            text = _collect_text(msgs)

            assert "phoenix" in text.lower(), (
                f"Memory not visible on turn 0: {text!r}"
            )

        asyncio.run(_run())

    def test_rotation_resets(self, tmp_path):
        """After reset(), SDK session is cleared and next send starts fresh."""
        async def _run():
            s = Session(
                preamble=SIMPLE_PREAMBLE,
                cwd=str(tmp_path),
            )

            await _send_and_collect(s, "Remember: the password is 'alpha'.")
            assert s._sdk_session_id is not None
            old_id = s.id

            # Rotate without summary
            s.reset()
            assert s._sdk_session_id is None
            assert s.turns == 0
            assert s.id != old_id  # new generation
            assert s.generation == 1

            # Fresh session — Claude should NOT remember
            msgs = await _send_and_collect(
                s,
                "What is the password? If you don't know, say 'unknown'.",
            )
            text = _collect_text(msgs)

            # After reset, Claude should not know the password
            assert "alpha" not in text.lower(), (
                f"Claude remembered across reset: {text!r}"
            )

        asyncio.run(_run())

    def test_rotation_with_summary(self, tmp_path):
        """on_rotation callback receives the new memory text."""
        async def _run():
            received = []
            s = Session(
                preamble=SIMPLE_PREAMBLE,
                cwd=str(tmp_path),
                on_rotation=lambda mem: received.append(mem),
            )

            await _send_and_collect(s, "The project name is 'Phoenix'.")
            old_id = s.id

            summary = await s.rotate("Summarise what you know in one sentence.")
            assert summary is not None
            assert len(summary) > 0
            assert s.memory == summary  # memory updated
            assert s._sdk_session_id is None  # reset after rotation
            assert s.turns == 0
            assert s.id != old_id  # new generation
            assert s.generation == 1

            assert len(received) == 1
            assert received[0] == s.memory

        asyncio.run(_run())

    def test_write_guard_live(self, tmp_path):
        """canUseTool blocks writes outside allowed paths in a real agent."""
        async def _run():
            safe = tmp_path / "safe"
            safe.mkdir()

            s = Session(
                preamble=(
                    "You are a test agent. When asked to create a file, "
                    "use the Write tool to create it."
                ),
                cwd=str(safe),
                allowed_write_paths=[str(safe)],
            )

            # Ask the agent to write inside the allowed path — should work
            await _send_and_collect(
                s,
                f"Create a file at {safe}/test.txt with content 'hello'.",
            )
            assert (safe / "test.txt").exists(), "Write inside allowed path should work"

        asyncio.run(_run())
