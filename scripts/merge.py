"""Merge worker — processes tasks in 'needs_merge' status.

Called once per daemon cycle. Scans for tasks with status 'needs_merge',
checks the repo's approval setting, and either merges automatically or
waits for manual approval. Processes one merge per cycle to avoid race
conditions.

Merge flow:
    1. Find oldest needs_merge task (ordered by updated_at, FIFO).
    2. Look up the task's repo and its approval config.
    3. If approval=auto  → merge immediately.
       If approval=manual → only merge if task.approval_status='approved'.
    4. To merge: git fetch, git merge <branch> into main, git push.
    5. On success: set task status to 'merged' (completed_at set automatically).
    6. On conflict: set task status to 'conflict', notify EM.
"""

import logging
import subprocess
from pathlib import Path

from scripts.task import list_tasks, get_task, change_status, update_task
from scripts.mailbox import send as send_message
from scripts.bootstrap import get_member_by_role

logger = logging.getLogger(__name__)


def _get_repo_clone_path(root: Path, repo_name: str) -> Path | None:
    """Resolve the path to a repo's full clone.

    Repos are stored in ~/.headcount/repos/<name>/ — we derive hc_home
    by walking up from the team root (root is <clone>/myteam/).
    """
    # The team root sits inside a repo clone: <hc_home>/repos/<repo>/myteam/
    # But hc_home may also be at a different level. Check environment first,
    # then fall back to convention.
    import os
    hc_home_env = os.environ.get("STANDUP_HQ")
    if hc_home_env:
        p = Path(hc_home_env) / "repos" / repo_name
        if p.is_dir():
            return p

    # Convention: root is <hc_home>/repos/<some_repo>/myteam/
    # so hc_home = root.parent.parent.parent
    hc_home = root.parent.parent.parent
    p = hc_home / "repos" / repo_name
    if p.is_dir():
        return p

    return None


def _get_repo_approval(root: Path, repo_name: str) -> str:
    """Get the approval mode for a repo ('auto' or 'manual').

    Reads from ~/.headcount/config.yaml. Defaults to 'manual'.
    """
    import os
    import yaml

    hc_home_env = os.environ.get("STANDUP_HQ")
    if hc_home_env:
        config_path = Path(hc_home_env) / "config.yaml"
    else:
        hc_home = root.parent.parent.parent
        config_path = hc_home / "config.yaml"

    if not config_path.exists():
        return "manual"

    data = yaml.safe_load(config_path.read_text()) or {}
    repos = data.get("repos", {})
    meta = repos.get(repo_name, {})
    return meta.get("approval", "manual")


def _get_needs_merge_tasks(root: Path) -> list[dict]:
    """Return tasks with status 'needs_merge', ordered by updated_at (FIFO)."""
    tasks = list_tasks(root, status="needs_merge")
    tasks.sort(key=lambda t: t.get("updated_at", ""))
    return tasks


def _do_merge(clone_path: Path, branch: str) -> tuple[bool, str]:
    """Perform the actual git merge of branch into main.

    Steps:
        1. git fetch origin
        2. git checkout main
        3. git pull origin main (ensure up to date)
        4. git merge <branch> --no-ff
        5. git push origin main

    Returns:
        (success: bool, detail: str)
    """
    try:
        # 1. Fetch
        result = subprocess.run(
            ["git", "fetch", "origin"],
            cwd=str(clone_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return False, f"git fetch failed: {result.stderr}"

        # 2. Checkout main
        result = subprocess.run(
            ["git", "checkout", "main"],
            cwd=str(clone_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return False, f"git checkout main failed: {result.stderr}"

        # 3. Pull latest main
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=str(clone_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return False, f"git pull failed: {result.stderr}"

        # 4. Merge the branch
        result = subprocess.run(
            ["git", "merge", branch, "--no-ff",
             "-m", f"Merge branch '{branch}'"],
            cwd=str(clone_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            # Abort the failed merge to restore clean state
            subprocess.run(
                ["git", "merge", "--abort"],
                cwd=str(clone_path),
                capture_output=True,
                timeout=10,
            )
            return False, f"Merge conflict: {result.stdout}\n{result.stderr}"

        # 5. Push to origin
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=str(clone_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return False, f"git push failed: {result.stderr}"

        return True, "Merge successful"

    except subprocess.TimeoutExpired:
        return False, "Git operation timed out"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def _notify_manager(root: Path, task: dict, detail: str) -> None:
    """Send a conflict notification to the engineering manager.

    The message is sent from the director (the daemon runs on the
    director's behalf) to the manager.
    """
    manager = get_member_by_role(root, "manager")
    if not manager:
        logger.warning("No manager found to notify about merge conflict")
        return

    director = get_member_by_role(root, "director")
    if not director:
        logger.warning("No director found to send merge conflict notification")
        return

    task_id = task["id"]
    branch = task.get("branch", "(unknown)")
    repo = task.get("repo", "(unknown)")
    assignee = task.get("assignee", "(unknown)")

    message = (
        f"MERGE CONFLICT on T{task_id:04d}\n"
        f"Repo: {repo}\n"
        f"Branch: {branch}\n"
        f"Assignee: {assignee}\n"
        f"Detail: {detail}\n\n"
        f"The task has been set to 'conflict' status. "
        f"The assignee should rebase and resolve the conflict."
    )

    send_message(root, director, manager, message)
    logger.info("Notified %s about merge conflict on T%04d", manager, task_id)


def merge_once(root: Path) -> int:
    """Run one merge cycle.

    Finds the oldest task in 'needs_merge' status and attempts to merge it.
    Processes at most one merge per cycle.

    Returns:
        Number of tasks merged (0 or 1).
    """
    tasks = _get_needs_merge_tasks(root)
    if not tasks:
        return 0

    for task in tasks:
        task_id = task["id"]
        repo_name = task.get("repo", "")
        branch = task.get("branch", "")

        if not repo_name or not branch:
            logger.debug(
                "Skipping T%04d: missing repo (%s) or branch (%s)",
                task_id, repo_name, branch,
            )
            continue

        # Check approval config
        approval = _get_repo_approval(root, repo_name)

        if approval == "manual":
            approval_status = task.get("approval_status", "")
            if approval_status != "approved":
                logger.debug(
                    "Skipping T%04d: manual approval required, "
                    "current approval_status=%r",
                    task_id, approval_status,
                )
                continue

        # Resolve repo clone path
        clone_path = _get_repo_clone_path(root, repo_name)
        if clone_path is None or not clone_path.is_dir():
            logger.warning(
                "Skipping T%04d: repo clone not found for %r",
                task_id, repo_name,
            )
            continue

        # Attempt the merge
        logger.info(
            "Merging T%04d: branch=%s repo=%s (approval=%s)",
            task_id, branch, repo_name, approval,
        )
        success, detail = _do_merge(clone_path, branch)

        if success:
            change_status(root, task_id, "merged")
            logger.info("T%04d merged successfully", task_id)
            return 1
        else:
            # Merge conflict or failure
            change_status(root, task_id, "conflict")
            _notify_manager(root, task, detail)
            logger.warning("T%04d merge failed: %s", task_id, detail)
            return 0  # Still processed one task — exit cycle

    return 0
