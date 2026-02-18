"""Unified agent runtime — single-turn executor.

The daemon dispatches ``run_turn()`` for each agent that has unread
messages.  Each call:

1. Reads unread inbox messages and selects a batch of ≤5 messages that
   share the same ``task_id`` as the first message.
2. Marks the selected messages as *seen*.
3. Resolves the task (if any) and all repo worktree paths.
4. Builds a user message (task context + conversation history + new
   messages) via ``Prompt``.
5. Sends the user message through the agent's ``Telephone`` — the
   persistent Claude subprocess — streaming tool summaries to the
   in-memory ring buffer, SSE subscribers, and the worklog.
6. Marks ALL selected messages as *processed*.
7. Optionally runs a reflection follow-up (1-in-10 coin flip) on the
   **same** Telephone (so the model has full conversation context).
8. Finalises the DB session: writes worklog, ends session.

``TelephoneExchange`` holds one ``Telephone`` per (team, agent) pair,
persisting across turns.  The daemon creates a single exchange at
startup and passes it to every ``run_turn()`` call.

DB session semantics are **unchanged**: ``start_session()`` /
``end_session()`` bracket each ``run_turn()`` call one-to-one, writing
a row to the ``sessions`` table.  The ``Telephone`` subprocess
lifetime is independent of DB sessions.
"""

import asyncio
import difflib
import logging
import os
import random
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from delegate.logging_setup import log_caller

from delegate.agent import (
    AgentLogger,
    _agent_dir,
    _read_state,
    _next_worklog_number,
    _process_turn_messages,
    ALLOWED_MODELS,
    DEFAULT_MODEL,
    DEFAULT_MANAGER_MODEL,
    MAX_BATCH_SIZE,
)
from delegate.mailbox import (
    read_inbox,
    mark_seen_batch,
    mark_processed_batch,
    Message,
)
from delegate.prompt import Prompt
from delegate.telephone import Telephone, TelephoneUsage
from delegate.task import format_task_id
from delegate.activity import broadcast as broadcast_activity, broadcast_thinking, mark_thinking_tool_break, clear_thinking_buffer, broadcast_turn_event
from delegate.paths import team_dir

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tools that agents are never allowed to use.
# Agents work in task-scoped worktrees and must not perform git operations
# that alter branch topology or interact with remotes — the merge worker
# handles rebasing and merging via controlled temporary branches.
DISALLOWED_TOOLS = [
    "Bash(git rebase:*)",
    "Bash(git merge:*)",
    "Bash(git pull:*)",
    "Bash(git push:*)",
    "Bash(git fetch:*)",
    "Bash(git checkout:*)",
    "Bash(git switch:*)",
    "Bash(git reset --hard:*)",
    "Bash(git reset --soft:*)",
    "Bash(git worktree:*)",
    "Bash(git branch:*)",
    "Bash(git remote:*)",
    "Bash(git filter-branch:*)",
    "Bash(git reflog expire:*)",
]

# Bash command substrings that are denied via the can_use_tool guard.
# These complement DISALLOWED_TOOLS — some patterns (like `sqlite3`) can't
# be expressed as tool patterns because the Claude tool schema uses a
# `git <subcommand>:*` format.
DENIED_BASH_PATTERNS = [
    "git push",
    "git rebase",
    "git merge",
    "git pull",
    "git fetch",
    "git checkout",
    "git switch",
    "git reset --hard",
    "git reset --soft",
    "git worktree",
    "git branch",
    "git remote",
    "git filter-branch",
    "git reflog expire",
    "rm -rf .git",
    "sqlite3 ",          # trailing space avoids matching variable names
    "DROP TABLE",
    "DELETE FROM",
]

# Reflection: 1-in-10 coin flip per turn
REFLECTION_PROBABILITY = 0.1

# In-memory turn counter per (team, agent) (module-level; single-process safe)
_turn_counts: dict[tuple[str, str], int] = {}


# ---------------------------------------------------------------------------
# AsyncRWLock — async read-write lock
# ---------------------------------------------------------------------------

class AsyncRWLock:
    """Async read-write lock.

    Multiple readers (agent turns) can hold the lock simultaneously.
    A single writer (merge worker) gets exclusive access -- blocks until
    all readers release and prevents new readers while held.
    """

    def __init__(self) -> None:
        self._cond = asyncio.Condition()
        self._readers: int = 0
        self._writer: bool = False

    async def acquire_read(self) -> None:
        async with self._cond:
            while self._writer:
                await self._cond.wait()
            self._readers += 1

    async def release_read(self) -> None:
        async with self._cond:
            self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    async def acquire_write(self) -> None:
        async with self._cond:
            while self._writer or self._readers > 0:
                await self._cond.wait()
            self._writer = True

    async def release_write(self) -> None:
        async with self._cond:
            self._writer = False
            self._cond.notify_all()


# ---------------------------------------------------------------------------
# TelephoneExchange — registry of persistent agent conversations
# ---------------------------------------------------------------------------

class TelephoneExchange:
    """Registry of persistent ``Telephone`` instances, one per (team, agent).

    Created once by the daemon and passed to every ``run_turn()`` call.
    ``close_all()`` is called during graceful shutdown to clean up all
    agent subprocesses.

    Also manages per-worktree AsyncRWLocks (keyed by (team, task_id)) that
    coordinate access between the turn dispatcher and merge worker.  Both run
    in the same event loop.

    Locking protocol:
    - Turn dispatcher: acquires READ lock via ``worktree_lock(team, task_id)``
      for the duration of the turn.  Multiple agent turns on the same task can
      hold the read lock simultaneously (e.g. manager + DRI reviewing together).
    - Merge worker: acquires WRITE lock via ``worktree_lock(team, task_id)``
      before ``git reset --hard`` in the agent worktree, releases after reset.
      The write lock waits for all active readers and blocks new readers.
    - This prevents the merge worker from resetting a worktree while an
      agent turn is actively writing to it.
    """

    def __init__(self) -> None:
        self._telephones: dict[tuple[str, str], Any] = {}  # -> Telephone
        self._worktree_locks: dict[tuple[str, int], AsyncRWLock] = {}

    # --- Telephone registry ---

    def get(self, team: str, agent: str) -> Any | None:
        """Return the Telephone for (team, agent), or None."""
        return self._telephones.get((team, agent))

    def put(self, team: str, agent: str, tel: Any) -> None:
        """Register a Telephone for (team, agent)."""
        self._telephones[(team, agent)] = tel

    def remove(self, team: str, agent: str) -> Any | None:
        """Remove and return the Telephone for (team, agent), or None."""
        return self._telephones.pop((team, agent), None)

    async def close_all(self) -> None:
        """Disconnect all Telephones (subprocess cleanup)."""
        for tel in self._telephones.values():
            try:
                await tel.close()
            except Exception:
                pass
        self._telephones.clear()

    # --- Worktree lock registry ---

    def worktree_lock(self, team: str, task_id: int) -> AsyncRWLock:
        """Return the AsyncRWLock for (team, task_id), creating it if needed.

        The lock is keyed by task_id (not agent name) because worktrees are
        per-task, not per-agent — and the merge worker only knows task_id.
        """
        key = (team, task_id)
        if key not in self._worktree_locks:
            self._worktree_locks[key] = AsyncRWLock()
        return self._worktree_locks[key]

    def discard_worktree_lock(self, team: str, task_id: int) -> None:
        """Remove the lock for (team, task_id) after task completion.

        Call this after a task reaches ``done`` or ``merge_failed`` to
        avoid unbounded growth of the lock registry.
        """
        self._worktree_locks.pop((team, task_id), None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def list_ai_agents(hc_home: Path, team: str) -> list[str]:
    """Return names of AI agents for a team (excludes human members).

    Used to filter ``agents_with_unread()`` results — humans should
    not have turns dispatched.
    """
    import yaml
    from delegate.paths import agents_dir as _agents_dir
    from delegate.config import get_human_members

    # Build set of human member names for fast lookup
    human_names = {m["name"] for m in get_human_members(hc_home)}

    adir = _agents_dir(hc_home, team)
    if not adir.is_dir():
        return []
    agents = []
    for d in sorted(adir.iterdir()):
        if not d.is_dir():
            continue
        # Skip human members
        if d.name in human_names:
            continue
        state_file = d / "state.yaml"
        if not state_file.exists():
            continue
        state = yaml.safe_load(state_file.read_text()) or {}
        # Also skip legacy "boss" role agents (pre-member model)
        if state.get("role") == "boss":
            continue
        agents.append(d.name)
    return agents


def _write_worklog(ad: Path, lines: list[str]) -> None:
    """Write worklog lines to the agent's logs directory."""
    log_num = _next_worklog_number(ad)
    logs_dir = ad / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{log_num}.worklog.md"
    log_path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Message selection — pick ≤K messages with the same task_id
# ---------------------------------------------------------------------------

def _select_batch(
    inbox: list[Message],
    max_size: int = MAX_BATCH_SIZE,
    *,
    human_name: str | None = None,
) -> list[Message]:
    """Select up to *max_size* messages from *inbox* that share the
    same ``task_id`` as the first message.

    If *human_name* is provided, the first human message (if any)
    determines the grouping anchor instead of the oldest message.
    **When the anchor is from the human, only human messages are
    included** — this guarantees a clean "human-directed turn" that
    the frontend can distinguish from internal coordination turns.

    The inbox is assumed to be sorted by id (oldest first).
    Both ``task_id = None`` and ``task_id = N`` are valid grouping keys.

    When task_id is None, messages are also grouped by sender to avoid
    mixing messages from different senders in the same batch.

    **Per-sender ordering invariant**: a sender is only eligible for
    the batch if their *earliest* unprocessed message matches the
    target.  This guarantees we never skip an earlier message from a
    sender to include a later one.
    """
    if not inbox:
        return []

    # --- Determine the anchor (which task_id to batch for) ---
    # Human messages get priority: use the human's first message as anchor.
    priority_name = human_name
    anchor = inbox[0]
    is_human_anchor = False
    if priority_name:
        for msg in inbox:
            if msg.sender == priority_name:
                anchor = msg
                is_human_anchor = True
                break

    target_task_id = anchor.task_id
    target_sender = anchor.sender if target_task_id is None else None

    # --- Human-only batch invariant ---
    # When the anchor is from the human, restrict the batch to human
    # messages only.  This ensures the turn is cleanly "human-directed"
    # so the frontend can show inline thinking in the chat panel.
    if is_human_anchor:
        batch: list[Message] = []
        for msg in inbox:
            if msg.sender != priority_name:
                continue
            batch.append(msg)
            if len(batch) >= max_size:
                break
        return batch

    # --- Per-sender eligibility ---
    # A sender is eligible only if their earliest inbox message matches
    # the target.  If sender A's first message is for a different task,
    # including any later message from A would violate arrival order.
    earliest_by_sender: dict[str, Message] = {}
    for msg in inbox:
        if msg.sender not in earliest_by_sender:
            earliest_by_sender[msg.sender] = msg

    eligible: set[str] = set()
    for sender, first_msg in earliest_by_sender.items():
        if first_msg.task_id != target_task_id:
            continue
        if target_task_id is None and first_msg.sender != target_sender:
            continue
        eligible.add(sender)

    # --- Collect matching messages from eligible senders ---
    batch = []
    for msg in inbox:
        if msg.sender not in eligible:
            continue
        if msg.task_id != target_task_id:
            continue
        if target_task_id is None and msg.sender != target_sender:
            continue
        batch.append(msg)
        if len(batch) >= max_size:
            break
    return batch


# ---------------------------------------------------------------------------
# Workspace resolution — multi-repo worktree paths
# ---------------------------------------------------------------------------

def _resolve_workspace(
    hc_home: Path,
    team: str,
    agent: str,
    task: dict | None,
) -> tuple[Path, dict[str, Path]]:
    """Determine the cwd and per-repo worktree paths for a turn.

    Returns ``(cwd, workspace_paths)`` where *cwd* is the working
    directory to pass to the SDK and *workspace_paths* maps each repo
    name to its worktree path (for the user message).

    Falls back to the agent's own workspace directory when there is no
    task or no repos.

    **Defense-in-depth**: if a task has repos but one or more worktrees
    are missing (daemon hasn't created them yet), the missing repos are
    logged as warnings and omitted from *workspace_paths*.  The agent
    still gets the fallback workspace — it can proceed with non-repo
    work but won't attempt to write code into a nonexistent worktree.
    """
    from delegate.repo import get_task_worktree_path

    ad = _agent_dir(hc_home, team, agent)
    fallback = ad / "workspace"
    fallback.mkdir(parents=True, exist_ok=True)

    if not task:
        return fallback, {}

    repos: list[str] = task.get("repo", [])
    if not repos:
        return fallback, {}

    workspace_paths: dict[str, Path] = {}
    cwd: Path = fallback

    for i, repo_name in enumerate(repos):
        wt = get_task_worktree_path(hc_home, team, repo_name, task["id"])
        if wt.is_dir():
            workspace_paths[repo_name] = wt
            if i == 0:
                cwd = wt  # first available worktree is the cwd
        else:
            logger.warning(
                "Worktree not yet available for %s/%s repo=%s — "
                "daemon may still be creating it",
                team, format_task_id(task["id"]), repo_name,
            )

    return cwd, workspace_paths


# ---------------------------------------------------------------------------
# Turn result
# ---------------------------------------------------------------------------

@dataclass
class TurnResult:
    """Result of a single agent turn."""

    agent: str
    team: str
    session_id: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read: int = 0
    cache_write: int = 0
    cost_usd: float = 0.0
    turns: int = 0
    error: str | None = None


# ---------------------------------------------------------------------------
# Tool-summary extractor (feeds ring buffer + SSE + worklog)
# ---------------------------------------------------------------------------

# MCP tool formatters — convert tool input dicts to human-readable (category, detail) tuples.
# Each lambda receives the tool's ``input`` dict and returns a (category, detail) tuple.
# Category groups related tools for display (e.g. "task", "message", "git", "repo").
MCP_TOOL_FORMATTERS: dict[str, Any] = {
    # Task management — category: "task"
    "task_create": lambda inp: (
        "task",
        f'create: "{inp.get("title", "")[:40]}"'
        + (f' ({inp["priority"]})' if inp.get("priority") and inp["priority"] != "medium" else ""),
    ),
    "task_assign": lambda inp: (
        "task",
        f'assign T{inp.get("task_id", 0):04d} to {inp.get("assignee", "?").title()}',
    ),
    "task_status": lambda inp: (
        "task",
        f'T{inp.get("task_id", 0):04d} -> {inp.get("new_status", "?")}',
    ),
    "task_comment": lambda inp: ("task", f'comment on T{inp.get("task_id", 0):04d}'),
    "task_show": lambda inp: ("task", f'show T{inp.get("task_id", 0):04d}'),
    "task_list": lambda inp: ("task", "list tasks"),
    "task_cancel": lambda inp: ("task", f'cancel T{inp.get("task_id", 0):04d}'),
    "task_attach": lambda inp: (
        "task",
        f'attach {os.path.basename(inp.get("file_path", "?"))} to T{inp.get("task_id", 0):04d}',
    ),
    "task_detach": lambda inp: (
        "task",
        f'detach {os.path.basename(inp.get("file_path", "?"))} from T{inp.get("task_id", 0):04d}',
    ),
    # Communication — category: "message"
    "mailbox_send": lambda inp: (
        "message",
        f'send to {inp.get("recipient", "?").title()}: "{(inp.get("message", "") or "")[:40]}"'
        + ("..." if len(inp.get("message", "") or "") > 40 else ""),
    ),
    "mailbox_inbox": lambda inp: ("message", "check inbox"),
    # Repository — category: "repo"
    "repo_list": lambda inp: ("repo", "list repos"),
    # Git — category: "git"
    "rebase_to_main": lambda inp: ("git", f'rebase T{inp.get("task_id", 0):04d} to main'),
}


def _extract_tool_summary(block: Any) -> tuple[str, str]:
    """Extract a ``(tool_name, detail)`` pair from an AssistantMessage block.

    Returns ``("", "")`` if the block is not a tool invocation.
    """
    if not hasattr(block, "name"):
        return "", ""

    name = block.name
    inp = getattr(block, "input", {}) or {}

    # Strip MCP namespace prefix so "mcp__delegate__task_create" -> "task_create"
    short_name = name.split("__")[-1] if name.startswith("mcp__") else name

    if name == "Bash":
        return name, (inp.get("command", "") or "")[:120]
    elif name in ("Edit", "Write", "Read", "MultiEdit"):
        return name, inp.get("file_path", "")
    elif name in ("Grep", "Glob"):
        return name, inp.get("pattern", "")
    elif short_name in MCP_TOOL_FORMATTERS:
        try:
            return MCP_TOOL_FORMATTERS[short_name](inp)
        except Exception as exc:  # noqa: BLE001
            logger.warning("MCP formatter error for %s: %s", name, exc)
            keys = ", ".join(sorted(inp.keys())[:3]) if inp else ""
            return short_name, f"{short_name}({keys})" if keys else short_name
    else:
        keys = ", ".join(sorted(inp.keys())[:3]) if inp else ""
        return short_name, f"{short_name}({keys})" if keys else short_name


def extract_edit_diff(block: Any) -> list[str] | None:
    """Extract up to 3 diff lines from an Edit or Write tool-use block.

    For ``Edit``: diffs ``old_string`` vs ``new_string`` from the tool input.
    For ``Write``: reads the existing file content from disk and diffs against
    the new ``content`` field.  If the file does not exist, every new line is
    treated as an addition.

    Returns a list of up to 3 lines from the first hunk (``+``, ``-``, or
    context lines — the ``---``/``+++`` header lines are skipped).  Returns
    ``None`` if the block is not an Edit/Write tool or if no meaningful diff
    can be produced.
    """
    if not hasattr(block, "name"):
        return None

    name = block.name
    inp = getattr(block, "input", {}) or {}

    if name == "Edit":
        old_text = inp.get("old_string", "") or ""
        new_text = inp.get("new_string", "") or ""
    elif name == "Write":
        file_path = inp.get("file_path", "") or ""
        new_text = inp.get("content", "") or ""
        try:
            old_text = Path(file_path).read_text(encoding="utf-8", errors="replace") if file_path else ""
        except OSError:
            old_text = ""
    else:
        return None

    if old_text == new_text:
        return None

    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff_lines: list[str] = []
    for line in difflib.unified_diff(old_lines, new_lines, lineterm=""):
        # Skip the --- / +++ header lines
        if line.startswith("---") or line.startswith("+++"):
            continue
        # Skip the @@ hunk header lines
        if line.startswith("@@"):
            continue
        # Strip trailing newlines for clean rendering
        diff_lines.append(line.rstrip("\n\r"))
        if len(diff_lines) >= 3:
            break

    return diff_lines if diff_lines else None


# ---------------------------------------------------------------------------
# Telephone creation helper
# ---------------------------------------------------------------------------

def _write_paths_for_role(
    hc_home: Path,
    team: str,
    agent: str,
    role: str,
) -> list[str]:
    """Return the base allowed-write paths for an agent based on its role.

    * **manager** — the entire team directory (manages all agents/tasks).
    * **everyone else** — agent's own directory + the team ``shared/`` folder.
      Per-task worktree paths are added dynamically each turn.
    """
    from delegate.paths import shared_dir, agent_dir as _ad

    if role == "manager":
        return [str(team_dir(hc_home, team))]

    return [
        str(_ad(hc_home, team, agent)),
        str(shared_dir(hc_home, team)),
    ]


def _repo_git_dirs(hc_home: Path, team: str) -> list[str]:
    """Return resolved ``.git/`` paths for every registered repo in *team*.

    These are added to the sandbox ``add_dirs`` so that ``git add`` /
    ``git commit`` inside a worktree can write to the repo's object store
    and index — without opening write access to the repo working tree
    itself or to arbitrary repos on the machine.
    """
    from delegate.repo import list_repos, get_repo_path

    git_dirs: list[str] = []
    for repo_name in list_repos(hc_home, team):
        try:
            real_repo = get_repo_path(hc_home, team, repo_name).resolve()
            git_dir = real_repo / ".git"
            if git_dir.is_dir():
                git_dirs.append(str(git_dir))
        except Exception:
            pass  # repo symlink broken or missing — skip
    return sorted(git_dirs)


def _create_telephone(
    hc_home: Path,
    team: str,
    agent: str,
    *,
    preamble: str,
    role: str = "engineer",
    model: str | None = None,
    ad: Path | None = None,
) -> Any:
    """Create a new Telephone for an agent.

    Uses the team home as ``cwd`` (per design: all agents get
    ``team_dir`` as their working directory).

    Write-path enforcement is role-based:
    * Manager — may write anywhere under the team directory.
    * Workers — may write to their own agent directory, the team
      ``shared/`` folder, and (added per-turn) task worktree paths.

    Sandbox ``add_dirs`` are narrowed to the team's working directory
    (not the entire DELEGATE_HOME) so that ``protected/`` and other
    teams' directories are never writable from bash:

    * **Team working directory** — the team's ``teams/<uuid>/`` dir.
    * **Platform temp directory** — for scratch files.
    * **Repo ``.git/`` directories** — workers only.  Allows ``git add``
      / ``git commit`` inside worktrees without opening the repo working
      tree.  Managers do NOT get ``.git/`` access (they don't work in
      worktrees).

    ``denied_bash_patterns`` adds a soft deny layer for dangerous
    commands that complement the ``disallowed_tools`` list.

    The ``on_rotation`` callback writes the rotation summary
    to the agent's ``context.md``.
    """
    if ad is None:
        ad = _agent_dir(hc_home, team, agent)

    def _on_rotation(memory: str | None) -> None:
        if memory:
            (ad / "context.md").write_text(memory)

    # Platform-appropriate temp directory (resolves macOS /tmp → /private/tmp)
    tmpdir = str(Path(tempfile.gettempdir()).resolve())

    # Sandbox add_dirs: team working directory + tmpdir.
    # Workers also get .git/ dirs for git add/commit in worktrees.
    # Managers do NOT get .git/ — they don't work in worktrees.
    team_working_dir = str(team_dir(hc_home, team))
    add_dirs = [team_working_dir, tmpdir]

    if role != "manager":
        # Repo .git/ dirs — allows git add/commit inside worktrees
        # without opening the repo working tree to arbitrary bash writes.
        git_dirs = _repo_git_dirs(hc_home, team)
        add_dirs.extend(git_dirs)

    # In-process MCP server — runs inside daemon, outside agent sandbox.
    # Gives agents safe access to DB/config via tool calls instead of CLI.
    from delegate.mcp_tools import create_agent_mcp_server

    mcp_server = create_agent_mcp_server(hc_home, team, agent)
    mcp_servers = {"delegate": mcp_server} if mcp_server is not None else None

    # Network allowlist — read from protected/network.yaml
    from delegate.network import get_allowed_domains
    allowed_domains = get_allowed_domains(hc_home)

    return Telephone(
        preamble=preamble,
        cwd=team_dir(hc_home, team),
        model=model,
        allowed_write_paths=_write_paths_for_role(hc_home, team, agent, role) + [tmpdir],
        add_dirs=add_dirs,
        disallowed_tools=DISALLOWED_TOOLS,
        denied_bash_patterns=DENIED_BASH_PATTERNS,
        on_rotation=_on_rotation,
        sandbox_enabled=True,
        mcp_servers=mcp_servers,
        allowed_domains=allowed_domains,
    )


# ---------------------------------------------------------------------------
# Inner helpers: stream turn messages through a Telephone
# ---------------------------------------------------------------------------

async def _stream_telephone(
    tel: Any,
    prompt: str,
    alog: AgentLogger,
    turn_tokens: TelephoneUsage,
    turn_tools: list[str],
    worklog_lines: list[str],
    *,
    agent: str,
    team: str,
    task_label: str,
    current_task_id: int | None,
) -> None:
    """Send a prompt through a Telephone, process each message."""
    # Telephone._track_message already updates tel.usage internally.
    # Snapshot before/after to compute the per-turn delta and add it
    # to the caller's accumulator.
    starting_usage = tel.total_usage()
    dummy = TelephoneUsage()  # throwaway so _process_turn_messages can do worklog/tools
    async for msg in tel.send(prompt):
        _process_turn_messages(
            msg, alog, dummy, turn_tools, worklog_lines,
            agent=agent, task_label=task_label,
        )
        if hasattr(msg, "content"):
            for block in msg.content:
                tool_name, detail = _extract_tool_summary(block)
                if tool_name:
                    diff = extract_edit_diff(block) if tool_name in ("Edit", "Write") else None
                    broadcast_activity(agent, team, tool_name, detail, task_id=current_task_id, diff=diff)
                    mark_thinking_tool_break(agent, team)
                elif hasattr(block, "text") and block.text:
                    broadcast_thinking(agent, team, block.text, task_id=current_task_id)

    turn_tokens += tel.total_usage() - starting_usage


# ---------------------------------------------------------------------------
# Core: run a single turn for one agent
# ---------------------------------------------------------------------------

async def run_turn(
    hc_home: Path,
    team: str,
    agent: str,
    *,
    exchange: TelephoneExchange,
) -> TurnResult:
    """Run a single turn for an agent.

    Selects ≤5 unread messages that share the same ``task_id``, resolves
    the task and worktree paths, builds a prompt with bidirectional
    history, executes the turn (streaming tool summaries to the activity
    ring buffer / SSE), then marks every selected message as processed.

    If the 1-in-10 reflection coin-flip lands, a second (reflection)
    turn is appended **on the same Telephone** so the model has full
    conversation context from the main turn.

    A persistent ``Telephone`` is reused across turns via the
    ``exchange``; the preamble is rebuilt each turn and the telephone is
    rotated if it changed.

    Write-path enforcement is role-based (see ``_write_paths_for_role``):
    managers may write anywhere under the team directory; workers may
    only write to their own agent directory, the team shared folder,
    and the current task's worktree paths.

    DB session semantics are unchanged: ``start_session()`` /
    ``end_session()`` bracket each ``run_turn()`` call one-to-one.

    Returns a ``TurnResult`` with token usage and cost.
    """
    from delegate.chat import (
        start_session,
        end_session,
        update_session_tokens,
        update_session_task,
    )

    alog = AgentLogger(agent)
    result = TurnResult(agent=agent, team=team)

    # --- Agent setup ---
    ad = _agent_dir(hc_home, team, agent)
    state = _read_state(ad)
    role = state.get("role", "engineer")

    # Set logging caller context for all log lines during this turn
    _prev_caller = log_caller.set(f"{agent}:{role}")
    # Resolve model: prefer direct 'model' field, fall back from legacy 'seniority'
    _SENIORITY_MAP = {"senior": "opus", "junior": "sonnet"}
    model = (
        state.get("model")
        or _SENIORITY_MAP.get(state.get("seniority", ""), None)
        or (DEFAULT_MANAGER_MODEL if role == "manager" else DEFAULT_MODEL)
    )
    token_budget = state.get("token_budget")
    max_turns = max(1, token_budget // 4000) if token_budget else None

    # --- Message selection: pick ≤5 with same task_id (human first) ---
    from delegate.config import get_default_human
    inbox = read_inbox(hc_home, team, agent, unread_only=True)
    batch = _select_batch(inbox, human_name=get_default_human(hc_home))

    if not batch:
        log_caller.reset(_prev_caller)
        return result  # nothing to do

    current_task_id: int | None = batch[0].task_id
    current_task: dict | None = None

    if current_task_id is not None:
        try:
            from delegate.task import get_task as _get_task
            current_task = _get_task(hc_home, team, current_task_id)
        except Exception:
            logger.debug("Could not resolve task %s", current_task_id)

    # --- Skip cancelled/done tasks: mark messages processed and return ---
    if current_task and current_task.get("status") in ("cancelled", "done"):
        logger.info(
            "Task %s is %s — discarding %d message(s) for %s",
            format_task_id(current_task_id), current_task["status"],
            len(batch), agent,
        )
        msg_ids = [m.id for m in batch if m.id is not None]
        if msg_ids:
            mark_seen_batch(hc_home, team, msg_ids)
            mark_processed_batch(hc_home, team, msg_ids)
        log_caller.reset(_prev_caller)
        return result

    # --- Acquire worktree read lock for the duration of this turn ---
    # Multiple agent turns on the same task can hold the read lock
    # simultaneously (e.g. manager and DRI both active). The merge worker
    # acquires a write lock before ``git reset --hard``, which waits for
    # all readers to finish and blocks new readers while held.
    worktree_lock = None
    if current_task_id is not None:
        worktree_lock = exchange.worktree_lock(team, current_task_id)
        await worktree_lock.acquire_read()

    # --- Workspace resolution ---
    workspace, workspace_paths = _resolve_workspace(
        hc_home, team, agent, current_task,
    )

    # --- Mark selected messages as seen ---
    seen_ids = [m.id for m in batch if m.id is not None]
    if seen_ids:
        mark_seen_batch(hc_home, team, seen_ids)

    for inbox_msg in batch:
        alog.message_received(inbox_msg.sender, len(inbox_msg.body))

    # --- Broadcast turn_started event ---
    primary_sender = batch[0].sender
    broadcast_turn_event('turn_started', agent, team=team, task_id=current_task_id, sender=primary_sender)

    # --- Start DB session (1:1 with run_turn) ---
    session_id = start_session(hc_home, team, agent, task_id=current_task_id)
    result.session_id = session_id

    alog.session_start_log(
        task_id=current_task_id,
        model=model,
        token_budget=token_budget,
        workspace=workspace,
        session_id=session_id,
    )

    # --- Build prompts ---
    prompt_builder = Prompt(hc_home, team, agent)

    preamble = prompt_builder.build_preamble()
    # Get or create Telephone; rotate if preamble changed, replace if
    # repo list changed (add_dirs is a subprocess-level setting).
    tel = exchange.get(team, agent)

    if tel is not None and role != "manager":
        # Check if registered repos changed (new repo added / removed).
        # add_dirs is baked into the subprocess — can't be changed via
        # rotation, so we must close + recreate.
        # Only workers get .git/ dirs; managers don't work in worktrees.
        expected_git_dirs = _repo_git_dirs(hc_home, team)
        current_git_dirs = sorted(
            d for d in (str(p) for p in tel.add_dirs)
            if d.endswith("/.git") or d.endswith("\\.git")
        )
        if expected_git_dirs != current_git_dirs:
            logger.info(
                "Repo list changed for %s/%s — replacing telephone "
                "(old=%d repos, new=%d repos)",
                team, agent, len(current_git_dirs), len(expected_git_dirs),
            )
            await tel.close()
            tel = None
            exchange.put(team, agent, None)

    if tel is not None:
        # Check if network allowlist changed.  allowed_domains is baked
        # into the sandbox config — must recreate on change.
        from delegate.network import get_allowed_domains
        current_domains = sorted(tel.allowed_domains)
        expected_domains = sorted(get_allowed_domains(hc_home))
        if current_domains != expected_domains:
            logger.info(
                "Network allowlist changed for %s/%s — replacing telephone",
                team, agent,
            )
            await tel.close()
            tel = None
            exchange.put(team, agent, None)

    if tel is not None and tel.model != model:
        logger.info(
            "Model changed for %s/%s (%s -> %s) — replacing telephone",
            team, agent, tel.model, model,
        )
        await tel.close()
        tel = None
        exchange.put(team, agent, None)

    if tel is not None and tel.preamble != preamble:
        logger.info("Preamble changed for %s/%s — rotating telephone", team, agent)
        await tel.rotate()
        tel.preamble = preamble
    if tel is None:
        tel = _create_telephone(
            hc_home, team, agent,
            preamble=preamble,
            role=role,
            model=model,
            ad=ad,
        )
        exchange.put(team, agent, tel)

    # --- Per-turn write-path update for workers ---
    # Managers already have access to the entire team directory (static).
    # Workers get their base paths (agent dir + shared) plus any task
    # worktree paths that change per-turn.
    if role != "manager" and workspace_paths:
        _tmpdir = str(Path(tempfile.gettempdir()).resolve())
        tel.allowed_write_paths = (
            _write_paths_for_role(hc_home, team, agent, role)
            + [str(p) for p in workspace_paths.values()]
            + [_tmpdir]
        )

    user_msg = prompt_builder.build_user_message(
        messages=batch,
        current_task=current_task,
        workspace_paths=workspace_paths or None,
    )

    task_label = format_task_id(current_task_id) if current_task_id else ""
    worklog_lines: list[str] = [
        f"# Worklog — {agent}",
        f"Task: {task_label}" if task_label else "Task: (none)",
        f"Session: {datetime.now(timezone.utc).isoformat()}",
        f"Messages in batch: {len(batch)}",
        f"\n## Turn 1\n{user_msg}",
    ]

    alog.turn_start(1, user_msg)

    # --- Main turn ---
    turn = TelephoneUsage()
    turn_tools: list[str] = []
    error_occurred = False

    stream_kw = dict(
        alog=alog,
        turn_tokens=turn,
        turn_tools=turn_tools,
        worklog_lines=worklog_lines,
        agent=agent,
        team=team,
        task_label=task_label,
        current_task_id=current_task_id,
    )

    try:
        try:
            await _stream_telephone(tel, user_msg, **stream_kw)

        except Exception as exc:
            alog.session_error(exc)
            result.error = str(exc)
            result.turns = 1
            error_occurred = True
            _mark_batch_processed(hc_home, team, batch)
    finally:
        try:
            end_session(
                hc_home, team, session_id,
                tokens_in=turn.input_tokens, tokens_out=turn.output_tokens,
                cost_usd=turn.cost_usd,
                cache_read_tokens=turn.cache_read_tokens,
                cache_write_tokens=turn.cache_write_tokens,
            )
        except Exception:
            logger.exception("Failed to end session")

    # Early return on error
    if error_occurred:
        _write_worklog(ad, worklog_lines)
        clear_thinking_buffer(agent, team)
        broadcast_turn_event('turn_ended', agent, team=team, task_id=current_task_id, sender=primary_sender)
        log_caller.reset(_prev_caller)
        if worktree_lock is not None:
            await worktree_lock.release_read()
        return result

    # --- Post-turn bookkeeping ---
    alog.turn_end(
        1,
        tokens_in=turn.input_tokens,
        tokens_out=turn.output_tokens,
        cost_usd=turn.cost_usd,
        cumulative_tokens_in=turn.input_tokens,
        cumulative_tokens_out=turn.output_tokens,
        cumulative_cost=turn.cost_usd,
        tool_calls=turn_tools or None,
    )

    update_session_tokens(
        hc_home, team, session_id,
        tokens_in=turn.input_tokens,
        tokens_out=turn.output_tokens,
        cost_usd=turn.cost_usd,
        cache_read_tokens=turn.cache_read_tokens,
        cache_write_tokens=turn.cache_write_tokens,
    )

    _mark_batch_processed(hc_home, team, batch)

    # Re-check task association
    if current_task_id is None:
        try:
            from delegate.task import list_tasks as _list_tasks
            open_tasks = _list_tasks(hc_home, team, assignee=agent, status="in_progress")
            if open_tasks:
                current_task_id = open_tasks[0]["id"]
                update_session_task(hc_home, team, session_id, current_task_id)
                alog.info(
                    "Task association updated | task=%s",
                    format_task_id(current_task_id),
                )
        except Exception:
            pass

    # --- Optional reflection turn (1-in-10 coin flip) ---
    total = TelephoneUsage(
        input_tokens=turn.input_tokens, output_tokens=turn.output_tokens,
        cache_read_tokens=turn.cache_read_tokens, cache_write_tokens=turn.cache_write_tokens,
        cost_usd=turn.cost_usd,
    )
    turn_num = 1

    _tc_key = (team, agent)
    _turn_counts[_tc_key] = _turn_counts.get(_tc_key, 0) + 1

    try:
        if random.random() < REFLECTION_PROBABILITY:
            turn_num = 2
            ref_msg = prompt_builder.build_reflection_message()
            worklog_lines.append(f"\n## Turn 2 (reflection)\n{ref_msg}")
            alog.turn_start(2, ref_msg)

            ref = TelephoneUsage()
            ref_tools: list[str] = []

            ref_stream_kw = dict(
                alog=alog,
                turn_tokens=ref,
                turn_tools=ref_tools,
                worklog_lines=worklog_lines,
                agent=agent,
                team=team,
                task_label=task_label,
                current_task_id=current_task_id,
            )

            try:
                # Reflection on the same Telephone — model has full
                # conversation context from the main turn.
                await _stream_telephone(tel, ref_msg, **ref_stream_kw)

                total += ref

                alog.turn_end(
                    2,
                    tokens_in=ref.input_tokens,
                    tokens_out=ref.output_tokens,
                    cost_usd=ref.cost_usd,
                    cumulative_tokens_in=total.input_tokens,
                    cumulative_tokens_out=total.output_tokens,
                    cumulative_cost=total.cost_usd,
                    tool_calls=ref_tools or None,
                )

                alog.info("Reflection turn completed")
            except Exception as exc:
                alog.error("Reflection turn failed: %s", exc)
    finally:
        result.tokens_in = total.input_tokens
        result.tokens_out = total.output_tokens
        result.cache_read = total.cache_read_tokens
        result.cache_write = total.cache_write_tokens
        result.cost_usd = total.cost_usd
        result.turns = turn_num

        try:
            update_session_tokens(
                hc_home, team, session_id,
                tokens_in=total.input_tokens,
                tokens_out=total.output_tokens,
                cost_usd=total.cost_usd,
                cache_read_tokens=total.cache_read_tokens,
                cache_write_tokens=total.cache_write_tokens,
            )
        except Exception:
            logger.exception("Failed to update session tokens")

        alog.session_end_log(
            turns=turn_num,
            tokens_in=total.input_tokens,
            tokens_out=total.output_tokens,
            cost_usd=total.cost_usd,
        )

        _write_worklog(ad, worklog_lines)

        # context.md is written by the Telephone's on_rotation callback
        # when the context window fills up and the session rotates.

        clear_thinking_buffer(agent, team)
        broadcast_turn_event('turn_ended', agent, team=team, task_id=current_task_id, sender=primary_sender)
        log_caller.reset(_prev_caller)

        # Release the worktree read lock now that the turn is fully complete.
        # Placed here (after all bookkeeping) so the merge worker waits for
        # the entire turn to finish, not just the tool calls.
        if worktree_lock is not None:
            await worktree_lock.release_read()

    return result


# ---------------------------------------------------------------------------
# Helpers (post-turn)
# ---------------------------------------------------------------------------

def _mark_batch_processed(hc_home: Path, team: str, batch: list[Message]) -> None:
    """Mark all messages in the batch as processed."""
    ids = [m.id for m in batch if m.id is not None]
    if ids:
        mark_processed_batch(hc_home, team, ids)
