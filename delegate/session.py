"""Bounded-context persistent session for the Claude Code SDK.

Standalone utility — no knowledge of Delegate's domain model (teams,
agents, tasks, worktrees).  Hand it a preamble and a working
directory, call ``send()`` repeatedly.  The class handles session
resumption, token accounting, permission enforcement via
``can_use_tool``, and automatic context-window rotation.

On the **first turn** of each generation the user message sent to
the SDK is::

    {preamble}

    {memory}

    {prompt}

On subsequent (resumed) turns only the raw ``prompt`` is sent — the
preamble and memory are already in the conversation history.

When the context window fills up, the session **auto-rotates**:

1. Ask the model to summarise its state (``rotation_prompt``).
2. Store the summary as the new ``memory``.
3. Call ``on_rotation(memory)`` so the caller can persist it.
4. Reset conversation state (SDK session, turns, tokens).
5. The next ``send()`` starts a fresh generation with the preamble
   and the updated memory.

Claude Code's own system prompt — which contains all tool-use
instructions — is never overridden.

Usage::

    session = Session(
        preamble="You are a senior Python engineer working on Acme.",
        cwd="/path/to/workdir",
        allowed_write_paths=["/path/to/workdir"],
    )

    async for msg in session.send("Fix the bug in main.py"):
        print(msg)

    # Later — session is automatically resumed.
    # If context is full, send() auto-rotates transparently.
    async for msg in session.send("Now add tests"):
        print(msg)

    # Restart with prior memory (loaded from context.md):
    session = Session(
        preamble="You are a senior Python engineer working on Acme.",
        memory=Path("context.md").read_text(),
        cwd="/path/to/workdir",
        on_rotation=lambda mem: Path("context.md").write_text(mem or ""),
    )
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable

logger = logging.getLogger(__name__)

# Sentinel for "argument not provided" (distinct from None).
_UNSET = object()


# ---------------------------------------------------------------------------
# Token / cost accounting
# ---------------------------------------------------------------------------

@dataclass
class SessionUsage:
    """Cumulative token usage for a session."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class Session:
    """Bounded-context persistent session for a Claude Code agent.

    Each ``send()`` call either starts a new conversation or resumes
    the previous one via the SDK's ``resume`` parameter.  Token usage
    is tracked; when it exceeds ``max_context_tokens`` the session
    auto-rotates — asking the model to summarise, replacing
    ``memory`` with the summary, and starting a fresh conversation —
    all transparently within ``send()``.

    **Preamble vs Memory**

    * ``preamble`` — static role instructions and constraints.  Never
      changes.  Included on the first turn of every generation.
    * ``memory`` — dynamic accumulated context.  Starts empty (or
      loaded from a prior ``context.md``).  Replaced with the
      rotation summary on each context-window rotation.  Also
      included on the first turn of every generation.

    On turn 0 of any generation the user message is::

        {preamble}\\n\\n{memory}\\n\\n{prompt}

    On turn N > 0, only ``prompt`` is sent — everything else is
    already in the conversation history.

    **Permissions** are enforced per-turn via ``can_use_tool``:

    * *Write isolation*: ``allowed_write_paths`` restricts where
      ``Edit`` / ``Write`` tools can operate.  Pass ``None`` for
      unrestricted writes (e.g. managers).
    * *Bash deny-list*: ``denied_bash_patterns`` blocks commands
      containing specified substrings (e.g. ``"git rebase"``).

    The class is deliberately free of any Delegate-specific concepts
    (teams, agents, mailbox, tasks).  It only depends on
    ``claude_code_sdk``.

    Args:
        preamble: Static role instructions prepended to the user
            message on the first turn of each generation.
        cwd: Working directory for the agent.
        memory: Dynamic context (e.g. loaded from a prior
            ``context.md``).  Included after the preamble on the first
            turn.  Replaced with the rotation summary on each rotation.
            Default ``""``.
        max_context_tokens: Auto-rotate when cumulative input tokens
            exceed this.  Default 80 000.
        rotation_prompt: Prompt sent to the model before rotating to
            extract a summary.  Set to ``None`` to skip
            summarisation (hard reset only).
        on_rotation: Callback invoked after rotation with the new
            ``memory`` text (or ``None`` if no summary was produced).
            Use this to persist ``context.md``.
        model: Model identifier (e.g. ``"claude-sonnet-4-20250514"``).
        allowed_write_paths: Paths where Edit/Write are permitted.
            Multiple paths supported (multi-repo).  ``None`` means
            unrestricted.  Resolved to absolute paths.
        denied_bash_patterns: Substrings to block in Bash commands.
        add_dirs: Extra directories to expose to the agent.
        permission_mode: SDK permission mode.  Default
            ``"bypassPermissions"``.
        disallowed_tools: Tool patterns to deny at the SDK level
            (complementary to ``can_use_tool``).
    """

    DEFAULT_ROTATION_PROMPT = (
        "Your session context is about to be rotated. "
        "Please write a concise summary of whatever you have learned - about"
        "the project, codebase, recent tasks, and any other information that may "
        "be useful to you in future sessions.\n"
        "This summary will be provided to you at the start of your "
        "next session so you can pick up where you left off."
    )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        *,
        preamble: str,
        cwd: str | Path,
        memory: str = "",
        max_context_tokens: int = 80_000,
        rotation_prompt: str | None = DEFAULT_ROTATION_PROMPT,
        on_rotation: Callable[[str | None], Any] | None = None,
        model: str | None = None,
        allowed_write_paths: list[str | Path] | None = None,
        denied_bash_patterns: list[str] | None = None,
        add_dirs: list[str | Path] | None = None,
        permission_mode: str = "bypassPermissions",
        disallowed_tools: list[str] | None = None,
    ):
        # Stable identity
        self.id: str = uuid.uuid4().hex

        self.preamble = preamble
        self.memory = memory
        self.cwd = Path(cwd).resolve()
        self.max_context_tokens = max_context_tokens
        self.rotation_prompt = rotation_prompt
        self.on_rotation = on_rotation
        self.model = model
        self.permission_mode = permission_mode
        self.add_dirs = [Path(p).resolve() for p in (add_dirs or [])]
        self.disallowed_tools = list(disallowed_tools or [])

        # Permission configuration
        self._allowed_write_paths: list[Path] | None = (
            [Path(p).resolve() for p in allowed_write_paths]
            if allowed_write_paths is not None
            else None
        )
        self._denied_bash_patterns: list[str] = list(denied_bash_patterns or [])

        # Mutable session state (reset on rotation)
        self._sdk_session_id: str | None = None
        self.usage = SessionUsage()
        self.turns: int = 0
        self.created_at: float = time.time()
        self.generation: int = 0  # increments on each rotation

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """Whether a resumable SDK session exists."""
        return self._sdk_session_id is not None

    @property
    def needs_rotation(self) -> bool:
        """Whether cumulative input tokens exceed the budget."""
        return self.usage.input_tokens > self.max_context_tokens

    @property
    def allowed_write_paths(self) -> list[Path] | None:
        """Absolute paths where Edit/Write are allowed (``None`` = unrestricted)."""
        return self._allowed_write_paths

    @allowed_write_paths.setter
    def allowed_write_paths(self, paths: list[str | Path] | None) -> None:
        self._allowed_write_paths = (
            [Path(p).resolve() for p in paths]
            if paths is not None
            else None
        )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def _build_turn0_prompt(self, prompt: str) -> str:
        """Build the composite first-turn message.

        Layout::

            {preamble}

            {memory}       ← only if non-empty

            {prompt}
        """
        parts = ["## PREAMBLE", self.preamble]
        if self.memory and self.memory.strip():
            parts.append("## MEMORY")
            parts.append(self.memory)
        parts.append(prompt)
        return "\n\n".join(parts)

    async def send(
        self,
        prompt: str,
        *,
        allowed_write_paths: Any = _UNSET,
    ) -> AsyncIterator[Any]:
        """Send a prompt and stream response messages.

        On the first turn of each generation the full composite
        message (``preamble + memory + prompt``) is sent.  On
        subsequent (resumed) turns only ``prompt`` is sent — the
        rest is already in the conversation history.

        If the context window is full (``needs_rotation``), the session
        automatically rotates before processing the prompt.

        Args:
            prompt: The user message.
            allowed_write_paths: Override write-path restrictions for
                this turn.  ``None`` = unrestricted; omit to keep the
                session default.

        Yields:
            SDK message objects (``AssistantMessage``, ``SystemMessage``,
            ``ResultMessage``, etc.).
        """
        # --- Auto-rotate if context is full ---
        if self.needs_rotation:
            await self.rotate()

        from claude_code_sdk import query as sdk_query

        if allowed_write_paths is _UNSET:
            effective_write_paths = self._allowed_write_paths
        elif allowed_write_paths is None:
            effective_write_paths = None
        else:
            effective_write_paths = [Path(p).resolve() for p in allowed_write_paths]

        options = self._build_options(self.cwd, effective_write_paths)

        # On the first turn of each generation, include preamble + memory.
        effective_prompt = (
            self._build_turn0_prompt(prompt)
            if self.turns == 0
            else prompt
        )

        # The SDK requires an AsyncIterable[dict] prompt (streaming mode)
        # when can_use_tool is set.  Wrap the string in a one-shot
        # generator yielding the correct message dict.
        prompt_arg: Any = effective_prompt
        if getattr(options, "can_use_tool", None) is not None:

            async def _as_stream():
                yield {
                    "type": "user",
                    "message": {"role": "user", "content": effective_prompt},
                }

            prompt_arg = _as_stream()

        async for msg in sdk_query(prompt=prompt_arg, options=options):
            self._track_message(msg)
            yield msg

        self.turns += 1

    async def rotate(self, summary_prompt: str | None = _UNSET) -> str | None:
        """Rotate the session — summarise, update memory, reset.

        If the session is active and a summary prompt is available
        (defaults to ``self.rotation_prompt``), it is sent to the
        current session and the model's text response becomes the
        new ``memory``.  The ``on_rotation`` callback is then invoked
        with the new memory, and conversation state is reset.

        Called automatically by ``send()`` when ``needs_rotation``
        is true.

        Args:
            summary_prompt: Override the rotation prompt for this call.
                Pass ``None`` to skip summarisation.  Omit to use the
                session's ``rotation_prompt``.

        Returns:
            The summary text (new memory), or ``None``.
        """
        prompt = self.rotation_prompt if summary_prompt is _UNSET else summary_prompt
        summary: str | None = None

        if prompt and self._sdk_session_id:
            parts: list[str] = []
            # Temporarily disable rotation to avoid infinite recursion:
            # this is a summary turn, not a real user turn.
            saved_max = self.max_context_tokens
            self.max_context_tokens = float("inf")  # type: ignore[assignment]
            try:
                async for msg in self.send(prompt):
                    if hasattr(msg, "content"):
                        for block in msg.content:
                            if hasattr(block, "text"):
                                parts.append(block.text)
            finally:
                self.max_context_tokens = saved_max
            summary = "\n".join(parts).strip() or None

        logger.info(
            "Session %s rotating (gen %d → %d, %d turns, %d input tokens)",
            self.id[:8], self.generation, self.generation + 1,
            self.turns, self.usage.input_tokens,
        )

        # Update memory with the summary (persists across reset).
        self.memory = summary or ""

        # Notify caller so they can persist to disk.
        if self.on_rotation is not None:
            self.on_rotation(self.memory)

        self.reset()
        return summary

    def reset(self) -> None:
        """Hard reset — discard conversation state and mint new id.

        **Does not clear ``memory``** — it persists across generations.
        The caller can set ``session.memory = ""`` explicitly if
        needed.
        """
        self.id = uuid.uuid4().hex
        self._sdk_session_id = None
        self.usage = SessionUsage()
        self.turns = 0
        self.created_at = time.time()
        self.generation += 1

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_options(self, cwd: Path, write_paths: list[Path] | None) -> Any:
        """Assemble ``ClaudeCodeOptions`` for the current turn.

        Never sets ``system_prompt`` — we rely on Claude Code's own
        system prompt for tool-use instructions.  Our preamble and
        memory are prepended to the user message in ``send()`` instead.
        """
        from claude_code_sdk import ClaudeCodeOptions

        kw: dict[str, Any] = {
            "cwd": str(cwd),
            "permission_mode": self.permission_mode,
        }

        # Resume existing session if we have one.
        if self._sdk_session_id:
            kw["resume"] = self._sdk_session_id

        if self.model:
            kw["model"] = self.model

        if self.add_dirs:
            kw["add_dirs"] = [str(d) for d in self.add_dirs]

        if self.disallowed_tools:
            kw["disallowed_tools"] = list(self.disallowed_tools)

        # Permission enforcement callback
        guard = self._make_guard(write_paths)
        if guard is not None:
            kw["can_use_tool"] = guard

        return ClaudeCodeOptions(**kw)

    def _make_guard(self, write_paths: list[Path] | None):
        """Build a ``can_use_tool`` callback for path/command enforcement.

        Returns ``None`` if there are no restrictions to enforce.
        """
        has_write_restriction = write_paths is not None
        has_bash_restriction = bool(self._denied_bash_patterns)

        if not has_write_restriction and not has_bash_restriction:
            return None

        # Capture in closure — these may differ per-turn.
        _write_paths = write_paths
        _bash_deny = self._denied_bash_patterns

        async def _guard(
            tool_name: str,
            tool_input: dict[str, Any],
            _context: Any,
        ):
            # --- Write-path isolation ---
            if _write_paths is not None and tool_name in ("Edit", "Write"):
                file_path = tool_input.get("file_path", "")
                if file_path:
                    resolved = Path(file_path).resolve()
                    if not any(
                        resolved == wp or _is_under(resolved, wp)
                        for wp in _write_paths
                    ):
                        return {
                            "behavior": "deny",
                            "message": (
                                f"Write denied: {file_path} is outside "
                                f"allowed paths {[str(p) for p in _write_paths]}"
                            ),
                        }

            # --- Bash deny-list ---
            if tool_name == "Bash" and _bash_deny:
                cmd = tool_input.get("command", "")
                for pattern in _bash_deny:
                    if pattern in cmd:
                        return {
                            "behavior": "deny",
                            "message": f"Command denied: contains '{pattern}'",
                        }

            return {"behavior": "allow"}

        return _guard

    def _track_message(self, msg: Any) -> None:
        """Update token accounting from a ``ResultMessage``."""
        # Import lazily to avoid hard dep at module level.
        try:
            from claude_code_sdk import ResultMessage
        except ImportError:
            return

        if not isinstance(msg, ResultMessage):
            return

        self._sdk_session_id = msg.session_id

        u = msg.usage or {}

        # based on live experiments, looks like all four of the below fields
        # are NOT cumulative, so we can just add them to the existing values.
        if u.get("input_tokens") is not None:
            self.usage.input_tokens += u.get("input_tokens")
        else:
            logger.warning("No input tokens found in usage")

        if u.get("output_tokens") is not None:
            self.usage.output_tokens += u.get("output_tokens")
        else:
            logger.warning("No output tokens found in usage")

        if u.get("cache_read_input_tokens") is not None:
            self.usage.cache_read_tokens += u.get("cache_read_input_tokens")
        else:
            logger.warning("No cache read tokens found in usage")

        if u.get("cache_creation_input_tokens") is not None:
            self.usage.cache_write_tokens += u.get("cache_creation_input_tokens")
        else:
            logger.warning("No cache creation tokens found in usage")

        if msg.total_cost_usd is not None:
            self.usage.cost_usd += msg.total_cost_usd
        else:
            logger.warning("No cost found in usage")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_under(child: Path, parent: Path) -> bool:
    """Check if *child* is a descendant of *parent* (both resolved)."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False
