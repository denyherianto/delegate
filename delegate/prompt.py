"""Prompt composition for agent turns.

The ``Prompt`` class provides a structured, composable way to build the
two pieces of text that feed into each agent turn:

1. **Preamble** (``build_preamble``) — the stable, per-agent role
   instructions that go into ``Telephone.preamble``.  This is
   everything that was previously the ``system_prompt``: charter,
   role, identity, commands, reflections, and reference-file pointers.

2. **User message** (``build_user_message``) — the volatile part:
   task context, conversation history, and new inbox messages.

Both methods produce byte-identical output to the old
``agent.build_system_prompt()`` and ``agent.build_user_message()``
functions — the extraction is a pure refactor with no behavioural
change.

Usage::

    p = Prompt(hc_home, team, agent)
    preamble = p.build_preamble()
    user_msg = p.build_user_message(messages=batch, current_task=task, workspace_paths=paths)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from delegate.paths import (
    agent_dir as _resolve_agent_dir,
    agents_dir,
    base_charter_dir,
)
from delegate.mailbox import read_inbox
from delegate.task import format_task_id
from delegate.agent import DEFAULT_MODEL, DEFAULT_MANAGER_MODEL, ALLOWED_MODELS

logger = logging.getLogger(__name__)


def collect_instruction_files(repo_path: Path) -> str:
    """Collect instruction files from standard locations in a repo."""
    candidates = [
        "CLAUDE.md",
        "AGENTS.md",
        ".claude/instructions.md",
        ".cursorrules",
        ".github/copilot-instructions.md",
    ]
    sections = []
    for candidate in candidates:
        # Case-insensitive file matching
        parent = repo_path / Path(candidate).parent
        target_name = Path(candidate).name.lower()
        if parent.is_dir():
            for entry in parent.iterdir():
                if entry.is_file() and entry.name.lower() == target_name:
                    content = entry.read_text().strip()
                    if content:
                        sections.append(
                            f"# Instructions from {entry.relative_to(repo_path)}\n\n{content}"
                        )
                    break  # take first case-insensitive match
    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Constants (mirrored from agent.py for identical output)
# ---------------------------------------------------------------------------

# Legacy seniority -> model mapping for backward compatibility
_SENIORITY_MAP = {"senior": "opus", "junior": "sonnet"}

# Context window: how many recent processed messages to include per turn
HISTORY_WITH_PEER = 8       # messages with the primary sender (both directions)
HISTORY_WITH_OTHERS = 4     # messages with anyone else

# Maximum messages to batch per turn (all must share the same task_id).
MAX_BATCH_SIZE = 5


class Prompt:
    """Composable prompt builder for a single agent.

    Instantiate once per agent; call ``build_preamble()`` at the start
    of each generation and ``build_user_message()`` every turn.

    All methods are deterministic and side-effect-free.
    """

    def __init__(self, hc_home: Path, team: str, agent: str) -> None:
        self.hc_home = hc_home
        self.team = team
        self.agent = agent

        self._ad = _resolve_agent_dir(hc_home, team, agent)
        self._state = yaml.safe_load((self._ad / "state.yaml").read_text()) or {}
        self._role = self._state.get("role", "engineer")
        # Resolve model: prefer direct 'model' field, fall back from legacy 'seniority'
        self._model = (
            self._state.get("model")
            or _SENIORITY_MAP.get(self._state.get("seniority", ""), None)
            or (DEFAULT_MANAGER_MODEL if self._role == "manager" else DEFAULT_MODEL)
        )

    # ------------------------------------------------------------------
    # Preamble (formerly: system prompt)
    # ------------------------------------------------------------------

    def build_preamble(self) -> str:
        """Build the full preamble — identical to ``agent.build_system_prompt()``.

        Uses the same f-string layout as the original to ensure
        byte-identical output (including blank lines and newlines).
        """
        charter_block = self._charter_block()
        role_block = self._section_role_charter()
        override_block = self._section_team_overrides()
        repo_instructions_block = self._section_repo_instructions()
        inlined_notes_block = self._section_inlined_notes()
        files_block = self._files_block()

        # The identity/commands section is inlined here so we can
        # replicate the exact f-string layout of the original.
        from delegate.bootstrap import get_member_by_role
        from delegate.config import get_default_human

        python = sys.executable
        hc_home = self.hc_home
        team = self.team
        agent = self.agent
        role = self._role
        model_name = self._model
        human_name = get_default_human(hc_home) or "human"
        manager_name = get_member_by_role(hc_home, team, "manager") or "delegate"

        return f"""\
=== TEAM CHARTER ===

{charter_block}{role_block}{override_block}{repo_instructions_block}

=== AGENT IDENTITY ===

You are {agent} (role: {role}, model: {model_name}), a team member in the Delegate system.
{human_name} is the human team member. You report to {manager_name} (manager).

CRITICAL: You communicate ONLY by using MCP tools. Your conversational
replies are NOT seen by anyone — they only go to an internal log. To send a
message that another agent or {human_name} will read, you MUST use the
mailbox_send tool.

The task_id parameter is REQUIRED when the message relates to a specific task.

=== AVAILABLE TOOLS ===

Communication:
  mailbox_send(recipient, message, task_id) — send a message to a team member
  mailbox_inbox() — check your unread messages

Task management:
  task_create(title, description?, priority?, repo?, depends_on?) — create a task
  task_list(status?, assignee?) — list tasks with optional filters
  task_show(task_id) — show task details
  task_assign(task_id, assignee) — assign a task
  task_status(task_id, new_status) — change task status
  task_comment(task_id, body) — add a comment to a task
  task_cancel(task_id) — cancel a task (manager only)
  task_attach(task_id, file_path) — attach a file to a task
  task_detach(task_id, file_path) — remove an attachment

Repository:
  repo_list() — list registered repositories

Use these tools directly — do NOT run CLI commands for messaging or task management.
For coding work, use standard bash, file editing, and git (add, commit, diff, log, status).
{inlined_notes_block}

REFERENCE FILES (read as needed):
{files_block}

Team data: {hc_home}/teams/{team}/"""

    def _charter_block(self) -> str:
        """Raw charter text — joined with ``---`` separators."""
        charter_dir = base_charter_dir()
        charter_files = [
            "values.md",
            "communication.md",
            "task-management.md",
            "code-review.md",
            "continuous-improvement.md",
        ]
        sections = []
        for fname in charter_files:
            fpath = charter_dir / fname
            if fpath.is_file():
                sections.append(fpath.read_text().strip())
        return "\n\n---\n\n".join(sections)

    def _section_role_charter(self) -> str:
        """Role-specific charter (e.g. roles/manager.md)."""
        _role_file_map = {"worker": "engineer.md"}
        role_charter_name = _role_file_map.get(self._role, f"{self._role}.md")
        role_path = base_charter_dir() / "roles" / role_charter_name
        if role_path.is_file():
            content = role_path.read_text().strip()
            if content:
                return f"\n\n---\n\n{content}"
        return ""

    def _section_team_overrides(self) -> str:
        """Per-team override charter."""
        from delegate.paths import team_dir as _team_dir
        override = _team_dir(self.hc_home, self.team) / "override.md"
        if override.exists():
            content = override.read_text().strip()
            if content:
                return f"\n\n---\n\n# Team Overrides\n\n{content}"
        return ""

    def _section_repo_instructions(self) -> str:
        """Instruction files collected from registered repos."""
        from delegate.repo import list_repos, get_repo_path
        repos = list_repos(self.hc_home, self.team)
        all_sections: list[str] = []
        for repo_name in repos:
            symlink = get_repo_path(self.hc_home, self.team, repo_name)
            real_path = symlink.resolve()
            if real_path.is_dir():
                collected = collect_instruction_files(real_path)
                if collected:
                    all_sections.append(collected)
        if not all_sections:
            return ""
        combined = "\n\n---\n\n".join(all_sections)
        return (
            "\n\n=== REPO INSTRUCTIONS ===\n"
            "(From instruction files found in registered repositories.)\n\n"
            f"{combined}"
        )

    def _section_inlined_notes(self) -> str:
        """Inlined reflections and feedback."""
        parts: list[str] = []

        reflections_path = self._ad / "notes" / "reflections.md"
        if reflections_path.is_file():
            content = reflections_path.read_text().strip()
            if content:
                parts.append(
                    "\n\n=== YOUR REFLECTIONS ===\n"
                    "(Lessons learned from past work — apply these going forward.)\n\n"
                    f"{content}"
                )

        feedback_path = self._ad / "notes" / "feedback.md"
        if feedback_path.is_file():
            content = feedback_path.read_text().strip()
            if content:
                parts.append(
                    "\n\n=== FEEDBACK YOU'VE RECEIVED ===\n"
                    "(From teammates and reviews — use this to improve.)\n\n"
                    f"{content}"
                )

        return "".join(parts)

    def _files_block(self) -> str:
        """Raw reference file pointers text."""
        _inlined_notes = {"reflections.md", "feedback.md"}
        roster = self.hc_home / "teams" / self.team / "roster.md"
        agents_root = agents_dir(self.hc_home, self.team)
        shared = self.hc_home / "teams" / self.team / "shared"

        file_pointers = [
            f"  {roster}                     — team roster",
            f"  {agents_root}/*/bio.md       — teammate backgrounds",
        ]

        journals_dir = self._ad / "journals"
        notes_dir = self._ad / "notes"
        if journals_dir.is_dir() and any(journals_dir.iterdir()):
            file_pointers.append(
                f"  {journals_dir}/T*.md          — your past task journals"
            )
        if notes_dir.is_dir():
            for note_file in sorted(notes_dir.glob("*.md")):
                if note_file.name in _inlined_notes:
                    continue
                file_pointers.append(
                    f"  {note_file}  — {note_file.stem.replace('-', ' ')}"
                )

        if shared.is_dir() and any(shared.iterdir()):
            file_pointers.append(
                f"  {shared}/                     — team shared docs, specs, scripts"
            )

        return "\n".join(file_pointers)

    # ------------------------------------------------------------------
    # User message
    # ------------------------------------------------------------------

    def build_user_message(
        self,
        *,
        messages: list | None = None,
        current_task: dict | None = None,
        workspace_paths: dict[str, Path] | None = None,
    ) -> str:
        """Build the user message — identical to ``agent.build_user_message()``."""
        parts: list[str] = []

        # --- Previous session context (cold start bootstrap) ---
        ctx_block = self._section_context_md()
        if ctx_block:
            parts.append(ctx_block)

        # --- Current task context ---
        task_block = self._section_task_context(current_task, workspace_paths)
        if task_block:
            parts.append(task_block)

        # --- Conversation history + new messages ---
        history_and_msgs = self._section_messages(messages, current_task)
        parts.append(history_and_msgs)

        # --- Other assigned tasks ---
        other_tasks = self._section_other_tasks(current_task)
        if other_tasks:
            parts.append(other_tasks)

        return "\n".join(parts)

    def _section_context_md(self) -> str:
        """Previous session context from context.md."""
        context = self._ad / "context.md"
        if context.exists() and context.read_text().strip():
            return f"=== PREVIOUS SESSION CONTEXT ===\n{context.read_text().strip()}"
        return ""

    def _section_task_context(
        self,
        current_task: dict | None,
        workspace_paths: dict[str, Path] | None = None,
    ) -> str:
        """Current task context block."""
        if not current_task:
            return ""

        parts: list[str] = []
        tid = format_task_id(current_task["id"])
        parts.append(f"=== CURRENT TASK — {tid} ===")
        parts.append(
            f"This turn is focused on {tid}. "
            "All your work and responses should relate to this task.\n"
        )
        parts.append(f"Title:       {current_task.get('title', '(untitled)')}")
        parts.append(f"Status:      {current_task.get('status', 'unknown')}")
        if current_task.get("description"):
            parts.append(f"Description: {current_task['description']}")
        if current_task.get("branch"):
            parts.append(f"Branch:      {current_task['branch']}")
        if current_task.get("priority"):
            parts.append(f"Priority:    {current_task['priority']}")
        if current_task.get("dri"):
            parts.append(f"DRI:         {current_task['dri']}")
        if workspace_paths:
            parts.append("\nRepo worktrees:")
            for rn, wp in workspace_paths.items():
                parts.append(f"  {rn}: {wp}")
            parts.append(
                "\n- Commit your changes frequently with clear messages."
                f"\n- Do NOT switch branches — stay on {current_task.get('branch', '')}."
                "\n- Your branch is local-only and will be merged by the merge worker when approved."
            )

        # Task activity
        try:
            from delegate.chat import get_task_timeline
            activity = get_task_timeline(self.hc_home, self.team, current_task["id"], limit=20)
            if activity:
                parts.append(f"\n--- Task Activity (latest {len(activity)} items) ---")
                for item in activity:
                    ts = item.get("timestamp", "")
                    if item.get("type") == "comment":
                        parts.append(f"[{ts}] [comment] {item['sender']}: {item['content']}")
                    elif item.get("type") == "event":
                        parts.append(f"[{ts}] {item['content']}")
                    elif item.get("type") == "chat":
                        parts.append(f"[{ts}] [msg] {item.get('sender', '?')} -> {item.get('recipient', '?')}: {item['content']}")
        except Exception:
            pass

        parts.append("")
        return "\n".join(parts)

    def _section_messages(
        self,
        messages: list | None,
        current_task: dict | None,
    ) -> str:
        """Conversation history + new messages."""
        from delegate.mailbox import recent_conversation

        parts: list[str] = []

        if messages is None:
            messages = list(read_inbox(self.hc_home, self.team, self.agent, unread_only=True))

        if messages:
            primary_sender = messages[0].sender

            history_peer = recent_conversation(
                self.hc_home, self.team, self.agent, peer=primary_sender,
                limit=HISTORY_WITH_PEER,
            )
            history_others = [
                m for m in recent_conversation(
                    self.hc_home, self.team, self.agent, limit=HISTORY_WITH_OTHERS * 2,
                )
                if m.sender != primary_sender and m.recipient != primary_sender
            ][:HISTORY_WITH_OTHERS]

            all_history = sorted(history_peer + history_others, key=lambda m: m.id or 0)
            if all_history:
                parts.append("=== RECENT CONVERSATION HISTORY ===")
                parts.append("(Previously processed messages — for context only.)\n")
                for msg in all_history:
                    direction = "→" if msg.sender == self.agent else "←"
                    parts.append(
                        f"[{msg.time}] {msg.sender} {direction} {msg.recipient}:\n{msg.body}\n"
                    )

        if messages:
            n = len(messages)
            parts.append(f"=== NEW MESSAGES ({n}) ===")
            for i, msg in enumerate(messages, 1):
                parts.append(f"--- Message {i}/{n} ---")
                parts.append(f"[{msg.time}] {msg.sender} → {msg.recipient}:\n{msg.body}")
            parts.append(
                f"\n\U0001f449 You have {n} message(s) above. "
                "You MUST address ALL of them in this turn — do not skip any. "
                "Handle each message: respond, take action, or acknowledge. "
                "If messages are related, you may address them together in a "
                "single coherent response."
            )
        else:
            parts.append("No new messages.")

        return "\n".join(parts)

    def _section_other_tasks(self, current_task: dict | None) -> str:
        """Other assigned tasks for awareness."""
        try:
            from delegate.task import list_tasks
            all_tasks = list_tasks(self.hc_home, self.team, assignee=self.agent)
            if all_tasks:
                current_id = current_task["id"] if current_task else None
                other_active = [
                    t for t in all_tasks
                    if t["status"] in ("todo", "in_progress") and t["id"] != current_id
                ]
                if other_active:
                    parts = ["\n=== YOUR OTHER ASSIGNED TASKS ==="]
                    parts.append("(For awareness — focus on the current task above.)")
                    for t in other_active:
                        parts.append(
                            f"- {format_task_id(t['id'])} ({t['status']}): {t['title']}"
                        )
                    return "\n".join(parts)
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------
    # Reflection message
    # ------------------------------------------------------------------

    def build_reflection_message(self) -> str:
        """Build a reflection-only user message — identical to
        ``agent.build_reflection_message()``.
        """
        journals_dir = self._ad / "journals"
        reflections_path = self._ad / "notes" / "reflections.md"
        feedback_path = self._ad / "notes" / "feedback.md"

        parts = [
            "=== REFLECTION TURN ===",
            "",
            "This is a dedicated reflection turn — no inbox messages to process.",
            "Please do the following:",
            f"1. Review your recent task journals in {journals_dir}/",
            f"2. Update {reflections_path} — bullet points only.",
            "   ONLY include reflections that are actionable in future situations.",
            "   Prune stale or obvious entries. Keep the file under 30 bullets.",
            "   Good: 'Always run tests before in_review — missed broken import.'",
            "   Bad: 'Worked on T0005, it was challenging but rewarding.'",
            f"3. Optionally review {feedback_path} and incorporate learnings.",
            "4. This file is inlined in your prompt, so future turns benefit "
            "from what you write here.",
        ]

        context = self._ad / "context.md"
        if context.exists() and context.read_text().strip():
            parts.insert(0, f"=== PREVIOUS SESSION CONTEXT ===\n{context.read_text().strip()}\n")

        return "\n".join(parts)
