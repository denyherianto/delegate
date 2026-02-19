"""Merge worker — rebase, test, fast-forward merge for approved tasks.

The merge sequence for a task in ``in_approval`` with an approved review
(or ``approval == 'auto'`` on the repo):

1. Create a disposable merge worktree + temp branch from the feature branch.
2. ``git rebase --onto main <base_sha> <temp>``  — rebase in the merge worktree.
3. If rebase conflicts:
   a. **Squash-reapply fallback**: create a fresh worktree from main,
      ``git diff main...<feature>`` and ``git apply``.  This often succeeds
      when commit-by-commit rebase fails (intermediate conflicts).
   b. If squash-apply also fails (true content conflict): capture the
      conflicting hunks, escalate to the manager with detailed context
      and ``rebase_to_main`` MCP tool instructions for the DRI.
4. Update ``base_sha`` on the task to current main HEAD (the rebase point).
5. Run pre-merge script / tests inside the **merge worktree** (not the
   agent worktree).  Each worktree has its own isolated environment set up
   by setup.sh, so no borrowing of the agent's environment is needed.
6. Remove the disposable merge worktrees.
7. Fast-forward main:
   - If user has ``main`` checked out AND dirty → **fail** (auto-retry).
   - If user has ``main`` checked out AND clean → ``git merge --ff-only``
     (updates ref AND working tree).
   - If user is on another branch → ``git update-ref`` with CAS (ref-only).
8. Set task to ``done``.
9. Clean up: feature branch and agent worktree removed on success.

Key invariants:
- The **agent worktree is never touched** during the merge process.
  No locking is required between the turn dispatcher and merge worker.
- The **main repo working directory is never touched** during rebase/test.
  The only time the working tree may advance is when the user has ``main``
  checked out cleanly — then ``merge --ff-only`` updates it in lockstep.
- On test failure: agent worktree is unchanged; merge worktrees are cleaned
  up.  Agent can fix and resubmit without recovery steps.
- All repos in a multi-repo task are rebased (or squash-applied) before
  tests run (all-or-nothing atomicity for the rebase step).

Failure handling:
- ``merge_task()`` is a **pure** merge function — it returns a result but
  never changes task status or assignee itself.
- ``merge_once()`` inspects the ``MergeFailureReason`` on failures and
  routes them:
  - **Retryable** failures (dirty main, transient ref conflicts) are
    silently retried up to 3 times (``merge_attempts``).
  - **Non-retryable** failures (rebase conflict, test failure, worktree
    error) are immediately escalated: status → ``merge_failed``, assign
    to manager, send notification.
  - After 3 retries, retryable failures also escalate to manager.

The merge worker is called from the daemon loop (via ``merge_once``).
"""

import enum
import logging
import os
import random
import subprocess
import time
import uuid
from pathlib import Path

from delegate.config import get_repo_approval
from delegate.notify import notify_conflict
from delegate.review import get_current_review
from delegate.task import (
    get_task, change_status, update_task, list_tasks,
    format_task_id, transition_task, assign_task,
)
from delegate.chat import log_event
from delegate.paths import team_dir as _team_dir
from delegate.repo import get_repo_path, remove_task_worktree

logger = logging.getLogger(__name__)

MAX_MERGE_ATTEMPTS = 3

# Exponential backoff for WORKTREE_ERROR retries.
# Delays per attempt (before jitter): ~5s, ~15s, ~45s
# Formula: BASE * (3 ** attempt_index) where attempt_index is 0-based.
_WORKTREE_RETRY_BASE = 5.0   # seconds
_WORKTREE_RETRY_JITTER = 0.3  # +-30% random jitter


def _worktree_retry_delay(attempt: int) -> float:
    """Compute the retry delay for a WORKTREE_ERROR.

    ``attempt`` is the 1-based attempt count (i.e. the count *after*
    incrementing, so attempt=1 is the first retry).  The delay grows
    exponentially: ~5s, ~15s, ~45s with +-30% jitter.

    Returns the delay in seconds (minimum 5s).
    """
    base = _WORKTREE_RETRY_BASE * (3 ** (attempt - 1))  # 5, 15, 45
    jitter = base * _WORKTREE_RETRY_JITTER * (2 * random.random() - 1)
    return max(5.0, base + jitter)


# ---------------------------------------------------------------------------
# Failure reason enum
# ---------------------------------------------------------------------------

class MergeFailureReason(enum.Enum):
    """Structured reasons for merge failures.

    Each member carries a human-readable ``short_message`` and a
    ``retryable`` flag that determines the routing policy in
    ``merge_once()``.
    """

    REBASE_CONFLICT   = ("Rebase conflict", False)
    SQUASH_CONFLICT   = ("True content conflict", False)
    PRE_MERGE_FAILED  = ("Pre-merge checks failed", False)
    WORKTREE_ERROR    = ("Could not create merge worktree", True)
    DIRTY_MAIN        = ("main has uncommitted changes", True)
    FF_NOT_POSSIBLE   = ("Fast-forward not possible", True)
    UPDATE_REF_FAILED = ("Atomic ref update failed", True)

    def __init__(self, short_message: str, retryable: bool):
        self.short_message = short_message
        self.retryable = retryable


class MergeResult:
    """Result of a merge attempt."""

    def __init__(
        self,
        task_id: int,
        success: bool,
        message: str,
        reason: MergeFailureReason | None = None,
        conflict_context: str = "",
    ):
        self.task_id = task_id
        self.success = success
        self.message = message
        self.reason = reason  # None on success
        self.conflict_context = conflict_context  # Rich hunk details for SQUASH_CONFLICT

    @property
    def retryable(self) -> bool:
        return self.reason.retryable if self.reason else False

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        tag = f", reason={self.reason.name}" if self.reason else ""
        return f"MergeResult({format_task_id(self.task_id)}, {status}, {self.message!r}{tag})"


def _run_git(args: list[str], cwd: str, **kwargs) -> subprocess.CompletedProcess:
    """Helper to run a git command."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Temp worktree lifecycle
# ---------------------------------------------------------------------------

def _merge_worktree_dir(hc_home: Path, team: str, uid: str, task_id: int) -> Path:
    """Worktree path for a merge attempt.

    Layout: ``teams/<team_uuid>/worktrees/_merge/<uid>/T<id>/``
    """
    return _team_dir(hc_home, team) / "worktrees" / "_merge" / uid / format_task_id(task_id)


def _create_temp_worktree(
    repo_dir: str,
    source_branch: str,
    wt_path: Path,
) -> tuple[str, str]:
    """Create a disposable worktree + temp branch from *source_branch*.

    The temp branch mirrors the feature branch structure with
    ``_merge/<uuid>`` inserted before the task-id segment::

        delegate/3f5776/myteam/T0001  →  delegate/3f5776/myteam/_merge/a1b2c3d4e5f6/T0001

    Returns ``(temp_branch_name, uid)``.

    Raises ``RuntimeError`` on failure.
    """
    uid = uuid.uuid4().hex[:12]

    # Derive temp branch name (insert _merge/<uid> before last segment)
    parts = source_branch.rsplit("/", 1)
    if len(parts) == 2:
        temp_branch = f"{parts[0]}/_merge/{uid}/{parts[1]}"
    else:
        temp_branch = f"_merge/{uid}/{source_branch}"

    # Create worktree + branch in one atomic command.
    # ``git worktree add -b <branch> <path> <start>`` creates a new branch
    # at <start> and checks it out in the new worktree.
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    result = _run_git(
        ["worktree", "add", "-b", temp_branch, str(wt_path), source_branch],
        cwd=repo_dir,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not create merge worktree: {result.stderr.strip()}"
        )
    return temp_branch, uid


def _remove_temp_worktree(repo_dir: str, wt_path: Path, temp_branch: str) -> None:
    """Remove a disposable merge worktree and its branch (best-effort)."""
    if wt_path.exists():
        result = _run_git(["worktree", "remove", str(wt_path), "--force"], cwd=repo_dir)
        if result.returncode != 0:
            logger.warning(
                "Failed to remove merge worktree at %s: %s",
                wt_path, result.stderr.strip(),
            )
    # Prune git's worktree metadata regardless of whether the directory was
    # removed — this cleans up stale .git/worktrees/<name>/ entries even if
    # the filesystem removal failed (e.g. due to permissions).
    _run_git(["worktree", "prune"], cwd=repo_dir)
    _run_git(["branch", "-D", temp_branch], cwd=repo_dir)
    # Clean up empty parent directories under _merge/
    try:
        parent = wt_path.parent
        while parent.name != "_merge" and parent != parent.parent:
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
            else:
                break
        # Remove _merge/ itself if empty
        if parent.name == "_merge" and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass  # best-effort cleanup


# ---------------------------------------------------------------------------
# Rebase (runs inside temp worktree)
# ---------------------------------------------------------------------------

def _rebase_onto_main(wt_dir: str, base_sha: str | None = None) -> tuple[bool, str]:
    """Rebase the current branch onto main inside the temp worktree.

    When *base_sha* is provided::

        git rebase --onto main <base_sha> HEAD

    This replays only the commits after ``base_sha`` onto current main.
    When *base_sha* is empty, falls back to ``git rebase main``.

    Returns ``(success, output)``.
    """
    if base_sha:
        rebase_cmd = ["rebase", "--onto", "main", base_sha]
    else:
        rebase_cmd = ["rebase", "main"]

    result = _run_git(rebase_cmd, cwd=wt_dir)
    if result.returncode != 0:
        _run_git(["rebase", "--abort"], cwd=wt_dir)
        return False, result.stderr + result.stdout

    return True, result.stdout


# ---------------------------------------------------------------------------
# Squash-reapply fallback (runs in a fresh temp worktree from main)
# ---------------------------------------------------------------------------

def _squash_reapply(
    repo_dir: str,
    branch: str,
    wt_dir: str,
) -> tuple[bool, str]:
    """Attempt to apply the feature branch's total diff onto main as one commit.

    When rebase fails due to intermediate commit conflicts, the total diff
    often still applies cleanly.  This creates a single squashed commit on
    top of main containing all the feature branch changes.

    The worktree at *wt_dir* must already be checked out at main (or a temp
    branch rooted at main).

    Returns ``(success, output)``.  On failure, *output* contains the
    ``git apply`` error which includes the conflicting file paths.
    """
    # Get the combined diff: main...branch (three-dot = changes on branch
    # since the merge-base, i.e. the feature's net contribution)
    diff_result = _run_git(["diff", f"main...{branch}"], cwd=repo_dir)
    if diff_result.returncode != 0:
        return False, f"Could not compute diff: {diff_result.stderr}"

    patch = diff_result.stdout
    if not patch.strip():
        # No diff — nothing to apply (branch is already at main)
        return True, "No changes to apply"

    # Apply the patch inside the temp worktree
    apply_result = subprocess.run(
        ["git", "apply", "--index", "--3way"],
        cwd=wt_dir,
        input=patch,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if apply_result.returncode != 0:
        return False, apply_result.stderr + apply_result.stdout

    # Commit the applied changes
    commit_result = _run_git(
        ["commit", "-m", f"squash-reapply: apply {branch} onto main"],
        cwd=wt_dir,
    )
    if commit_result.returncode != 0:
        return False, f"Commit after apply failed: {commit_result.stderr}"

    return True, commit_result.stdout


def _capture_conflict_hunks(
    repo_dir: str,
    branch: str,
    base_sha: str | None = None,
) -> str:
    """Capture human-readable conflict context when both rebase and squash fail.

    Identifies the specific files where the feature branch and main diverge
    on the same lines.

    Returns a formatted string suitable for embedding in a notification
    message to the manager/delegate.
    """
    # Find the merge base
    mb_ref = base_sha or "main"
    merge_base_result = _run_git(["merge-base", "main", branch], cwd=repo_dir)
    if merge_base_result.returncode == 0:
        mb_ref = merge_base_result.stdout.strip()

    # What changed on main since the merge-base
    main_diff = _run_git(["diff", "--name-only", f"{mb_ref}..main"], cwd=repo_dir)
    main_files = set(main_diff.stdout.strip().splitlines()) if main_diff.returncode == 0 else set()

    # What changed on the feature branch since the merge-base
    branch_diff = _run_git(["diff", "--name-only", f"{mb_ref}..{branch}"], cwd=repo_dir)
    branch_files = set(branch_diff.stdout.strip().splitlines()) if branch_diff.returncode == 0 else set()

    # Overlapping files are the conflict candidates
    overlap = sorted(main_files & branch_files)
    if not overlap:
        return "Could not identify specific conflicting files."

    parts = [f"Conflicting files ({len(overlap)}):"]
    for f in overlap[:10]:  # cap at 10 to keep message reasonable
        parts.append(f"  - {f}")

    if len(overlap) > 10:
        parts.append(f"  ... and {len(overlap) - 10} more files")

    return "\n".join(parts)


def _indent(text: str, spaces: int) -> str:
    """Indent each line of *text* by *spaces* spaces."""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.splitlines())


# ---------------------------------------------------------------------------
# Pre-merge tests (runs inside agent worktree)
# ---------------------------------------------------------------------------

def _run_pre_merge(
    wt_dir: str,
    hc_home: Path | None = None,
    team: str | None = None,
    repo_name: str | None = None,
) -> tuple[bool, str]:
    """Run pre-merge validation inside the agent worktree.

    Executes in two steps:
    1. Source ``.delegate/setup.sh`` (if present) to activate the environment
       (e.g. ``source .venv/bin/activate``, ``export PATH=...``).
    2. Source ``.delegate/premerge.sh`` (if present) to run the test suite.

    Both scripts are *sourced* (not executed) so that environment mutations
    (activated virtualenvs, exported variables) from setup carry forward
    into the test run.

    Graceful degradation: if a script is missing, log a warning and continue.
    A missing premerge script is not a failure — it means the repo hasn't
    adopted the convention yet.

    Returns ``(success, output)``.
    """
    wt_path = Path(wt_dir)
    setup_script = wt_path / ".delegate" / "setup.sh"
    test_script = wt_path / ".delegate" / "premerge.sh"

    # Build a single shell command that:
    # 1. Sources setup.sh if it exists (warns + continues if missing).
    # 2. Sources premerge.sh if it exists (warns + skips if missing).
    # 3. Fails (propagates exit code) if premerge.sh exits non-zero.
    #
    # Each script is sourced so env changes (venv activation, PATH exports)
    # survive into subsequent commands within the same shell.

    setup_exists = setup_script.exists()
    test_exists = test_script.exists()

    if not setup_exists:
        logger.warning("%s: .delegate/setup.sh not found — skipping env setup", wt_dir)
    if not test_exists:
        logger.warning("%s: .delegate/premerge.sh not found — skipping pre-merge tests", wt_dir)
        return True, ".delegate/premerge.sh not found — skipping pre-merge tests"

    # Build the shell command: optionally source setup, then source premerge.
    # We always run in a login-ish shell so that standard env is available.
    shell_parts: list[str] = []
    if setup_exists:
        shell_parts.append(". ./.delegate/setup.sh")
    shell_parts.append(". ./.delegate/premerge.sh")
    shell_cmd = " && ".join(shell_parts)

    try:
        result = subprocess.run(
            ["/bin/bash", "-c", shell_cmd],
            cwd=wt_dir,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=600,
            env=os.environ.copy(),
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            # Include last 50 lines of output in failure message
            lines = output.splitlines()
            tail = "\n".join(lines[-50:]) if len(lines) > 50 else output
            return False, f".delegate/premerge.sh exited {result.returncode}:\n{tail}"
        return True, f"Pre-merge checks passed:\n{output}"
    except subprocess.TimeoutExpired:
        return False, ".delegate/premerge.sh timed out after 600 seconds."
    except OSError as exc:
        return False, f"Pre-merge script failed to start: {exc}"


# Keep old names as aliases for backward compatibility
_run_tests = _run_pre_merge
_run_pipeline = _run_pre_merge


# ---------------------------------------------------------------------------
# Fast-forward merge (operates on refs only — no checkout needed)
# ---------------------------------------------------------------------------

def _ff_merge(repo_dir: str, branch: str) -> tuple[bool, str]:
    """Fast-forward merge the branch into main.

    Behaviour depends on the user's checkout state in the main repo:

    - **main checked out + dirty** → fail (protect uncommitted work).
    - **main checked out + clean** → ``git merge --ff-only`` (updates ref
      AND working tree so the user doesn't see phantom dirty files).
    - **other branch checked out** → ``git update-ref`` with CAS (ref-only,
      user's working tree is untouched).

    Returns ``(success, output)``.
    """
    # Get branch tip
    branch_result = _run_git(["rev-parse", branch], cwd=repo_dir)
    if branch_result.returncode != 0:
        return False, f"Could not resolve {branch}: {branch_result.stderr}"
    branch_tip = branch_result.stdout.strip()

    # Verify branch is a descendant of main (fast-forward check)
    ancestor_check = _run_git(
        ["merge-base", "--is-ancestor", "main", branch], cwd=repo_dir,
    )
    if ancestor_check.returncode != 0:
        return False, f"Fast-forward not possible: {branch} is not a descendant of main"

    # Check what the user has checked out in the main repo
    head_result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir)
    user_branch = head_result.stdout.strip() if head_result.returncode == 0 else ""

    if user_branch == "main":
        # User is on main — check for uncommitted changes
        status_result = _run_git(["status", "--porcelain"], cwd=repo_dir)
        dirty = status_result.stdout.strip()
        if dirty:
            return False, (
                "Main repo has uncommitted changes on main — "
                "commit or stash them before merging.\n"
                f"Dirty files:\n{dirty[:500]}"
            )

        # Clean main checkout: use merge --ff-only to update ref + working tree
        result = _run_git(["merge", "--ff-only", branch], cwd=repo_dir)
        if result.returncode != 0:
            return False, f"Fast-forward merge failed: {result.stderr}"
        return True, f"main fast-forwarded to {branch_tip[:12]} (working tree updated)"

    else:
        # User is on another branch: move ref only via atomic CAS
        main_result = _run_git(["rev-parse", "main"], cwd=repo_dir)
        if main_result.returncode != 0:
            return False, f"Could not resolve main: {main_result.stderr}"
        main_tip = main_result.stdout.strip()

        result = _run_git(
            ["update-ref", "refs/heads/main", branch_tip, main_tip],
            cwd=repo_dir,
        )
        if result.returncode != 0:
            return False, f"Atomic update-ref failed (concurrent push?): {result.stderr}"
        return True, f"main fast-forwarded to {branch_tip[:12]} (ref-only, user on {user_branch})"


def _ff_merge_to_sha(repo_dir: str, tip_sha: str) -> tuple[bool, str]:
    """Fast-forward merge main to a specific commit SHA.

    Used after the disposable worktree is removed — we have the rebased tip
    SHA but no longer have a branch ref for it (the temp branch is gone).

    Behaviour mirrors ``_ff_merge``:
    - main checked out + dirty → fail (protect uncommitted work)
    - main checked out + clean → ``git merge --ff-only <sha>``
    - other branch checked out → ``git update-ref`` CAS to sha

    Returns ``(success, output)``.
    """
    # Verify tip_sha is an ancestor of nothing — just check it exists
    verify = _run_git(["cat-file", "-e", tip_sha], cwd=repo_dir)
    if verify.returncode != 0:
        return False, f"Commit not found: {tip_sha}"

    # Verify tip is a descendant of main (fast-forward check)
    ancestor_check = _run_git(
        ["merge-base", "--is-ancestor", "main", tip_sha], cwd=repo_dir,
    )
    if ancestor_check.returncode != 0:
        return False, f"Fast-forward not possible: {tip_sha[:12]} is not a descendant of main"

    # Check what the user has checked out in the main repo
    head_result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir)
    user_branch = head_result.stdout.strip() if head_result.returncode == 0 else ""

    if user_branch == "main":
        # User is on main — check for uncommitted changes
        status_result = _run_git(["status", "--porcelain"], cwd=repo_dir)
        dirty = status_result.stdout.strip()
        if dirty:
            return False, (
                "Main repo has uncommitted changes on main — "
                "commit or stash them before merging.\n"
                f"Dirty files:\n{dirty[:500]}"
            )

        result = _run_git(["merge", "--ff-only", tip_sha], cwd=repo_dir)
        if result.returncode != 0:
            return False, f"Fast-forward merge failed: {result.stderr}"
        return True, f"main fast-forwarded to {tip_sha[:12]} (working tree updated)"

    else:
        # User is on another branch: move ref only via atomic CAS
        main_result = _run_git(["rev-parse", "main"], cwd=repo_dir)
        if main_result.returncode != 0:
            return False, f"Could not resolve main: {main_result.stderr}"
        main_tip = main_result.stdout.strip()

        result = _run_git(
            ["update-ref", "refs/heads/main", tip_sha, main_tip],
            cwd=repo_dir,
        )
        if result.returncode != 0:
            return False, f"Atomic update-ref failed (concurrent push?): {result.stderr}"
        return True, f"main fast-forwarded to {tip_sha[:12]} (ref-only, user on {user_branch})"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _other_unmerged_tasks_on_branch(
    hc_home: Path,
    team: str,
    branch: str,
    exclude_task_id: int,
) -> bool:
    """Check whether any other task shares *branch* and is not yet done.

    Returns ``True`` when at least one other task on the same branch still
    has a non-``done`` status, meaning the branch should be kept alive.
    """
    all_tasks = list_tasks(hc_home, team)
    for t in all_tasks:
        if t["id"] == exclude_task_id:
            continue
        if t.get("branch") == branch and t.get("status") != "done":
            return True
    return False


def _cleanup_after_merge(
    hc_home: Path,
    team: str,
    task_id: int,
    branch: str,
    repos: list[str],
    repo_dirs: dict[str, str],
    temp_worktrees: dict[str, tuple[Path, str]],
) -> None:
    """Clean up after a successful merge.

    Removes temp worktrees/branches, and if no sibling tasks share the
    feature branch, also removes the feature branch and agent worktree.
    """
    # 1. Remove temp worktrees and branches
    for repo_name, (wt_path, temp_branch) in temp_worktrees.items():
        _remove_temp_worktree(repo_dirs[repo_name], wt_path, temp_branch)

    # 2. Clean up feature branch + agent worktree (if no siblings need it)
    shared = _other_unmerged_tasks_on_branch(hc_home, team, branch, exclude_task_id=task_id)
    if shared:
        logger.info(
            "Skipping branch deletion for %s — other unmerged tasks share branch %s",
            format_task_id(task_id), branch,
        )
        return

    for rn in repos:
        rd = repo_dirs[rn]
        # 1. Remove the worktree directory first
        try:
            remove_task_worktree(hc_home, team, rn, task_id)
        except Exception as exc:
            logger.warning(
                "Could not remove agent worktree for %s (%s): %s",
                format_task_id(task_id), rn, exc,
            )
        # 2. Prune so git knows the branch is no longer checked out
        _run_git(["worktree", "prune"], cwd=rd)
        # 3. Now delete the branch (use -D because rebase changes commit SHAs,
        #    making git think the branch isn't "fully merged")
        result = _run_git(["branch", "-D", branch], cwd=rd)
        if result.returncode != 0:
            logger.warning(
                "Failed to delete branch %s in %s: %s",
                branch, rn, result.stderr,
            )


# ---------------------------------------------------------------------------
# Main merge sequence
# ---------------------------------------------------------------------------

def merge_task(
    hc_home: Path,
    team: str,
    task_id: int,
    skip_tests: bool = False,
) -> MergeResult:
    """Execute the full merge sequence for a task.

    This is a **pure** merge function: it attempts rebase → test →
    ff-merge and returns a ``MergeResult``.  It does **not** change the
    task's status or assignee — that is the caller's responsibility
    (``merge_once``).

    Flow:
    1. Rebase ALL repos in disposable merge worktrees (all-or-nothing: if
       any rebase fails, no agent worktrees are touched).
    2. Update ``base_sha`` on the task to current main HEAD.
    3. Run pre-merge tests **in the merge worktree** (not the agent
       worktree).  Each worktree has its own isolated environment via
       setup.sh, so no borrowing of the agent's worktree is needed.
    4. Remove the disposable merge worktrees.
    5. Fast-forward main to the rebased tip SHA.
    6. Clean up: feature branch + agent worktree removed on success.

    The agent's worktree is never touched during the merge process.
    No locking is required.

    Args:
        hc_home: Delegate home directory.
        team: Team name.
        task_id: Task ID.
        skip_tests: Skip test execution (for emergencies).

    Returns:
        MergeResult indicating success or failure (with reason).
    """
    task = get_task(hc_home, team, task_id)
    branch = task.get("branch", "")
    repos: list[str] = task.get("repo", [])

    if not branch:
        return MergeResult(task_id, False, "No branch set on task",
                           reason=MergeFailureReason.WORKTREE_ERROR)

    if not repos:
        return MergeResult(task_id, False, "No repo set on task",
                           reason=MergeFailureReason.WORKTREE_ERROR)

    # Resolve all repos and verify they exist
    repo_dirs: dict[str, str] = {}
    for repo_name in repos:
        repo_dir = get_repo_path(hc_home, team, repo_name)
        real_repo = repo_dir.resolve()
        if not real_repo.is_dir():
            return MergeResult(task_id, False, f"repo not found: {real_repo}",
                               reason=MergeFailureReason.WORKTREE_ERROR)
        repo_dirs[repo_name] = str(real_repo)

    # Log merge started with attempt number for clarity on retries
    merge_attempts = task.get("merge_attempts", 0)
    attempt_num = merge_attempts + 1
    log_event(hc_home, team, f"{format_task_id(task_id)} merge started ({branch}), attempt #{attempt_num}", task_id=task_id)

    base_sha_dict: dict = task.get("base_sha", {})
    merge_base_dict: dict[str, str] = {}
    merge_tip_dict: dict[str, str] = {}

    # Track temp worktrees and rebased tips
    temp_worktrees: dict[str, tuple[Path, str]] = {}  # repo_name -> (wt_path, temp_branch)
    rebased_tips: dict[str, str] = {}  # repo_name -> rebased tip SHA

    # -----------------------------------------------------------------------
    # Phase 1: Rebase ALL repos in disposable worktrees.
    # All-or-nothing: if any rebase fails, no agent worktrees are touched.
    # -----------------------------------------------------------------------

    for repo_name in repos:
        repo_str = repo_dirs[repo_name]

        # Step 1: Create a disposable worktree + temp branch from the feature branch.
        uid = uuid.uuid4().hex[:12]
        wt_path = _merge_worktree_dir(hc_home, team, uid, task_id)
        try:
            temp_branch, uid = _create_temp_worktree(repo_str, branch, wt_path)
        except RuntimeError as exc:
            log_event(
                hc_home, team,
                f"{format_task_id(task_id)} could not create merge worktree ({repo_name})",
                task_id=task_id,
            )
            for rn, (twp, tb) in temp_worktrees.items():
                _remove_temp_worktree(repo_dirs[rn], twp, tb)
            return MergeResult(task_id, False, str(exc),
                               reason=MergeFailureReason.WORKTREE_ERROR)
        temp_worktrees[repo_name] = (wt_path, temp_branch)
        wt_str = str(wt_path)

        # Step 2: Rebase the TEMP branch onto main (inside the temp worktree).
        base_sha = base_sha_dict.get(repo_name, "")
        ok, output = _rebase_onto_main(wt_str, base_sha=base_sha)
        if not ok:
            _remove_temp_worktree(repo_str, wt_path, temp_branch)
            del temp_worktrees[repo_name]

            log_event(
                hc_home, team,
                f"{format_task_id(task_id)} rebase conflict in {repo_name}, "
                f"trying squash-reapply fallback",
                task_id=task_id,
            )
            logger.info(
                "%s: rebase failed for %s, attempting squash-reapply",
                format_task_id(task_id), repo_name,
            )

            squash_uid = uuid.uuid4().hex[:12]
            squash_wt_path = _merge_worktree_dir(hc_home, team, squash_uid, task_id)
            squash_wt_path.parent.mkdir(parents=True, exist_ok=True)
            squash_branch = f"_merge/{squash_uid}/squash-{format_task_id(task_id)}"

            create_result = _run_git(
                ["worktree", "add", "-b", squash_branch, str(squash_wt_path), "main"],
                cwd=repo_str,
            )
            if create_result.returncode != 0:
                for rn, (twp, tb) in temp_worktrees.items():
                    _remove_temp_worktree(repo_dirs[rn], twp, tb)
                log_event(
                    hc_home, team,
                    f"{format_task_id(task_id)} squash-reapply worktree creation failed ({repo_name})",
                    task_id=task_id,
                )
                return MergeResult(
                    task_id, False,
                    f"Rebase conflict in {repo_name} and could not create squash worktree: "
                    f"{create_result.stderr[:200]}",
                    reason=MergeFailureReason.REBASE_CONFLICT,
                )

            squash_ok, squash_output = _squash_reapply(
                repo_str, branch, str(squash_wt_path),
            )

            if not squash_ok:
                _remove_temp_worktree(repo_str, squash_wt_path, squash_branch)
                for rn, (twp, tb) in temp_worktrees.items():
                    _remove_temp_worktree(repo_dirs[rn], twp, tb)

                conflict_ctx = _capture_conflict_hunks(
                    repo_str, branch, base_sha=base_sha,
                )
                log_event(
                    hc_home, team,
                    f"{format_task_id(task_id)} true content conflict in {repo_name}, "
                    f"squash-reapply also failed",
                    task_id=task_id,
                )
                return MergeResult(
                    task_id, False,
                    f"True content conflict in {repo_name}: {squash_output[:200]}",
                    reason=MergeFailureReason.SQUASH_CONFLICT,
                    conflict_context=conflict_ctx,
                )

            log_event(
                hc_home, team,
                f"{format_task_id(task_id)} squash-reapply succeeded for {repo_name}",
                task_id=task_id,
            )
            logger.info(
                "%s: squash-reapply succeeded for %s",
                format_task_id(task_id), repo_name,
            )
            wt_path = squash_wt_path
            temp_branch = squash_branch
            temp_worktrees[repo_name] = (wt_path, temp_branch)
            wt_str = str(wt_path)

        # Collect the rebased tip SHA from the temp worktree.
        tip_result = _run_git(["rev-parse", "HEAD"], cwd=wt_str)
        if tip_result.returncode != 0:
            for rn, (twp, tb) in temp_worktrees.items():
                _remove_temp_worktree(repo_dirs[rn], twp, tb)
            return MergeResult(
                task_id, False,
                f"Could not determine rebased tip in {repo_name}: {tip_result.stderr}",
                reason=MergeFailureReason.WORKTREE_ERROR,
            )
        rebased_tips[repo_name] = tip_result.stdout.strip()

    # -----------------------------------------------------------------------
    # Phase 2: Update base_sha on the task to current main HEAD.
    # -----------------------------------------------------------------------

    # Record current main HEAD (used to update base_sha)
    main_head_dict: dict[str, str] = {}
    for repo_name in repos:
        mr = _run_git(["rev-parse", "main"], cwd=repo_dirs[repo_name])
        main_head_dict[repo_name] = mr.stdout.strip() if mr.returncode == 0 else ""

    update_task(hc_home, team, task_id, base_sha=main_head_dict)

    # -----------------------------------------------------------------------
    # Phase 3: Run pre-merge tests in the merge worktree.
    # The merge worktree has setup.sh/premerge.sh (inherited from the feature
    # branch) and runs its own isolated environment via setup.sh.
    # The agent's worktree is never touched.
    # -----------------------------------------------------------------------

    if not skip_tests:
        for repo_name in repos:
            merge_wt_path, _ = temp_worktrees[repo_name]
            ok, output = _run_pre_merge(str(merge_wt_path), hc_home=hc_home, team=team, repo_name=repo_name)
            if not ok:
                log_event(
                    hc_home, team,
                    f"{format_task_id(task_id)} merge blocked — pre-merge checks failed ({repo_name})",
                    task_id=task_id,
                )
                # Clean up merge worktrees on test failure
                for rn, (twp, tb) in temp_worktrees.items():
                    _remove_temp_worktree(repo_dirs[rn], twp, tb)
                temp_worktrees.clear()
                return MergeResult(
                    task_id, False,
                    f"Pre-merge checks failed in {repo_name}: {output[:200]}",
                    reason=MergeFailureReason.PRE_MERGE_FAILED,
                )

    # Remove all disposable merge worktrees — tests are done.
    for repo_name, (wt_path, temp_branch) in temp_worktrees.items():
        _remove_temp_worktree(repo_dirs[repo_name], wt_path, temp_branch)
    temp_worktrees.clear()

    # -----------------------------------------------------------------------
    # Phase 4: Fast-forward merge main to the rebased tip SHA.
    # -----------------------------------------------------------------------

    for repo_name in repos:
        repo_str = repo_dirs[repo_name]
        rebased_tip = rebased_tips[repo_name]

        pre_merge = _run_git(["rev-parse", "main"], cwd=repo_str)
        merge_base_dict[repo_name] = pre_merge.stdout.strip() if pre_merge.returncode == 0 else ""

        ok, output = _ff_merge_to_sha(repo_str, rebased_tip)
        if not ok:
            log_event(
                hc_home, team,
                f"{format_task_id(task_id)} merge failed ({repo_name}), attempt #{attempt_num}",
                task_id=task_id,
            )
            if "uncommitted" in output.lower():
                reason = MergeFailureReason.DIRTY_MAIN
            elif "not a descendant" in output.lower() or "not possible" in output.lower():
                reason = MergeFailureReason.FF_NOT_POSSIBLE
            elif "update-ref failed" in output.lower() or "concurrent" in output.lower():
                reason = MergeFailureReason.UPDATE_REF_FAILED
            else:
                reason = MergeFailureReason.FF_NOT_POSSIBLE
            return MergeResult(
                task_id, False,
                f"Merge failed in {repo_name}: {output[:200]}",
                reason=reason,
            )

        post_merge = _run_git(["rev-parse", "main"], cwd=repo_str)
        merge_tip_dict[repo_name] = post_merge.stdout.strip() if post_merge.returncode == 0 else ""

    # Step 5: Record per-repo merge_base and merge_tip, then mark as done.
    update_task(hc_home, team, task_id, merge_base=merge_base_dict, merge_tip=merge_tip_dict)
    log_event(hc_home, team, f"{format_task_id(task_id)} merged to main \u2713", task_id=task_id)
    change_status(hc_home, team, task_id, "done")

    # Step 6: Clean up feature branch + agent worktree (temp WTs already removed).
    _cleanup_after_merge(hc_home, team, task_id, branch, repos, repo_dirs, {})

    return MergeResult(task_id, True, "Merged successfully")


def _get_manager_name(hc_home: Path, team: str) -> str:
    """Look up the manager agent name for this team."""
    from delegate.bootstrap import get_member_by_role
    return get_member_by_role(hc_home, team, "manager") or "delegate"


def _handle_merge_failure(
    hc_home: Path,
    team: str,
    task_id: int,
    result: MergeResult,
) -> None:
    """Route a merge failure based on the failure reason.

    - **Retryable** failures: increment ``merge_attempts``.  If still below
      ``MAX_MERGE_ATTEMPTS``, the task stays in ``merging`` and will be
      retried on the next daemon cycle.  Otherwise, escalate.
    - **Non-retryable** failures (or max retries exhausted): set status to
      ``merge_failed``, assign to manager, send ``notify_conflict``.
    """
    reason = result.reason
    if reason is None:
        reason = MergeFailureReason.WORKTREE_ERROR  # defensive fallback

    task = get_task(hc_home, team, task_id)
    detail = reason.short_message
    manager = _get_manager_name(hc_home, team)

    if reason.retryable:
        current_attempts = task.get("merge_attempts", 0) + 1
        task_updates: dict = dict(
            merge_attempts=current_attempts,
            status_detail=detail,
        )

        if current_attempts < MAX_MERGE_ATTEMPTS:
            # For WORKTREE_ERROR, schedule with exponential backoff so the
            # daemon doesn't busy-loop while an agent turn holds the lock.
            if reason is MergeFailureReason.WORKTREE_ERROR:
                delay = _worktree_retry_delay(current_attempts)
                task_updates["retry_after"] = time.time() + delay
                logger.info(
                    "%s: WORKTREE_ERROR, retry in %.0fs (attempt %d/%d)",
                    format_task_id(task_id), delay,
                    current_attempts, MAX_MERGE_ATTEMPTS,
                )
            else:
                # Silent retry: stay in 'merging' — merge_once will re-process
                logger.info(
                    "%s: retryable failure (%s), attempt %d/%d — will retry",
                    format_task_id(task_id), reason.name,
                    current_attempts, MAX_MERGE_ATTEMPTS,
                )
            update_task(hc_home, team, task_id, **task_updates)
            return

        update_task(hc_home, team, task_id, **task_updates)

        # Max retries exhausted → escalate
        logger.warning(
            "%s: retryable failure (%s) but max attempts (%d) reached — escalating",
            format_task_id(task_id), reason.name, MAX_MERGE_ATTEMPTS,
        )

    # Escalate: merge_failed + assign to manager + notify
    update_task(hc_home, team, task_id, status_detail=detail)
    transition_task(hc_home, team, task_id, "merge_failed", manager)
    notify_conflict(
        hc_home, team, task,
        conflict_details=f"{detail}: {result.message[:500]}",
        conflict_context=result.conflict_context,
    )


def merge_once(
    hc_home: Path,
    team: str,
) -> list[MergeResult]:
    """Scan for tasks ready to merge and process them.

    Two categories of tasks are processed:

    1. **Newly approved** — ``status == 'in_approval'`` with an approved
       review (or ``approval == 'auto'``).  These transition to ``merging``
       on first attempt.
    2. **Retrying** — ``status == 'merging'`` with ``merge_attempts > 0``
       (a previous attempt hit a retryable failure and stayed in
       ``merging``).

    On failure, ``_handle_merge_failure()`` routes the outcome: retryable
    failures stay in ``merging`` (up to ``MAX_MERGE_ATTEMPTS``), while
    non-retryable failures escalate to ``merge_failed``.

    Args:
        hc_home: Delegate home directory.
        team: Team name.

    Returns list of merge results.
    """
    results = []
    manager = _get_manager_name(hc_home, team)
    processed_ids: set[int] = set()

    # --- 1. Newly approved tasks ---
    for task in list_tasks(hc_home, team, status="in_approval"):
        task_id = task["id"]
        repos: list[str] = task.get("repo", [])

        if not repos:
            continue

        approval_mode = get_repo_approval(hc_home, team, repos[0])

        ready = False
        if approval_mode == "auto":
            ready = True
        elif approval_mode == "manual":
            review = get_current_review(hc_home, team, task_id)
            if review and review.get("verdict") == "approved":
                ready = True
            else:
                logger.debug(
                    "%s: needs human approval (verdict=%s)",
                    task_id, review.get("verdict") if review else "no review",
                )
        else:
            logger.warning(
                "%s: unknown approval mode '%s' for repos %s",
                task_id, approval_mode, repos,
            )

        if not ready:
            continue

        # Transition to merging with assignee = manager
        transition_task(hc_home, team, task_id, "merging", manager)

        result = merge_task(hc_home, team, task_id)
        results.append(result)
        processed_ids.add(task_id)

        if not result.success:
            _handle_merge_failure(hc_home, team, task_id, result)

    # --- 2. Process tasks in 'merging' status (retries) ---
    for task in list_tasks(hc_home, team, status="merging"):
        task_id = task["id"]
        if task_id in processed_ids:
            continue
        attempts = task.get("merge_attempts", 0)

        # Skip tasks that are scheduled for a future retry (exponential backoff).
        retry_after = task.get("retry_after")
        if retry_after and time.time() < retry_after:
            logger.debug(
                "%s: retry_after in %.0fs — skipping",
                format_task_id(task_id), retry_after - time.time(),
            )
            continue

        # Clear any stale retry_after before attempting so a success doesn't
        # leave the field set (it also gets cleared on success below).
        if retry_after is not None:
            update_task(hc_home, team, task_id, retry_after=None)

        logger.info(
            "%s: %s merge (attempt %d/%d)",
            format_task_id(task_id),
            "retrying" if attempts > 0 else "starting",
            attempts + 1, MAX_MERGE_ATTEMPTS,
        )
        result = merge_task(hc_home, team, task_id)
        results.append(result)

        if result.success:
            # Successful merge — clear retry_after (task is done, but belt+suspenders)
            # merge_task sets status to 'done', so this is just defensive cleanup.
            pass
        else:
            _handle_merge_failure(hc_home, team, task_id, result)

    return results
