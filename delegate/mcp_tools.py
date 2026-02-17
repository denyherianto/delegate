"""In-process MCP tools for agent data/metadata operations.

These tools run inside the daemon process (outside the OS sandbox) and
provide agents with safe access to the database and configuration files
without requiring shell access to ``protected/``.

Each tool closure captures ``hc_home``, ``team``, and ``agent`` so that:
- Agents cannot impersonate other agents (sender identity is baked in).
- All operations go through the model layer (same validation as CLI).
- The database and config files are only modified via trusted code paths.

Admin operations (``delegate network``, ``delegate team``, ``delegate workflow``)
are intentionally NOT exposed here.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _text_result(text: str) -> dict:
    """Wrap a plain string into the MCP tool result format."""
    return {"content": [{"type": "text", "text": text}]}


def _json_result(data: Any) -> dict:
    """Wrap a JSON-serialisable object into the MCP tool result format."""
    return _text_result(json.dumps(data, indent=2, default=str))


def _error_result(msg: str) -> dict:
    """Return an MCP tool error result."""
    return {"content": [{"type": "text", "text": f"ERROR: {msg}"}], "isError": True}


# ---------------------------------------------------------------------------
# Tool factory — builds all MCP tools for a given agent context
# ---------------------------------------------------------------------------


def build_agent_tools(hc_home: Path, team: str, agent: str) -> list:
    """Build the list of MCP tool definitions for an agent.

    Returns a list of decorated tool functions ready to pass to
    ``create_sdk_mcp_server(tools=[...])``.

    Raises ``ImportError`` if ``claude_agent_sdk`` is not available.
    """
    from claude_agent_sdk import tool

    # -----------------------------------------------------------------------
    # Mailbox tools
    # -----------------------------------------------------------------------

    @tool(
        "mailbox_send",
        "Send a message to another team member. This is the ONLY way to communicate with others.",
        {
            "type": "object",
            "properties": {
                "recipient": {"type": "string"},
                "message": {"type": "string"},
                "task_id": {
                    "type": ["integer", "null"],
                    "description": "Optional task ID to associate the message with. Omit or pass null for messages not related to a specific task.",
                },
            },
            "required": ["recipient", "message"],
        },
    )
    async def mailbox_send(args: dict) -> dict:
        try:
            from delegate.mailbox import send

            recipient = args["recipient"]
            message = args["message"]
            task_id = args.get("task_id")
            # Defense-in-depth: convert 0 to None (task IDs start at 1;
            # some MCP clients may default missing int params to 0)
            if task_id == 0:
                task_id = None

            send(
                hc_home,
                team,
                agent,           # sender is baked in — no impersonation
                recipient,
                message,
                task_id=task_id,
            )
            result = f"Message sent to {recipient}"
            if task_id:
                result += f" (task T{task_id:04d})"
            return _text_result(result)
        except Exception as e:
            logger.exception("mailbox_send failed")
            return _error_result(str(e))

    @tool(
        "mailbox_inbox",
        "Check your inbox for unread messages.",
        {},
    )
    async def mailbox_inbox(args: dict) -> dict:
        try:
            from delegate.mailbox import read_inbox

            messages = read_inbox(hc_home, team, agent, unread_only=True)
            if not messages:
                return _text_result("No unread messages.")
            result = []
            for m in messages:
                entry = {
                    "from": m.sender,
                    "body": m.body,
                    "task_id": m.task_id,
                    "timestamp": str(m.timestamp) if hasattr(m, "timestamp") else None,
                }
                result.append(entry)
            return _json_result(result)
        except Exception as e:
            logger.exception("mailbox_inbox failed")
            return _error_result(str(e))

    # -----------------------------------------------------------------------
    # Task tools
    # -----------------------------------------------------------------------

    @tool(
        "task_create",
        "Create a new task for the team. Returns the created task.",
        {
            "title": str,
            "description": str,
            "priority": str,
            "repo": str,
            "depends_on": str,
        },
    )
    async def task_create(args: dict) -> dict:
        try:
            from delegate.task import create_task

            kwargs: dict[str, Any] = {
                "title": args["title"],
                "assignee": agent,  # default to creating agent
            }
            if args.get("description"):
                kwargs["description"] = args["description"]
            if args.get("priority"):
                kwargs["priority"] = args["priority"]
            if args.get("repo"):
                kwargs["repo"] = args["repo"]
            if args.get("depends_on"):
                # Parse comma-separated task IDs
                try:
                    deps = [int(x.strip()) for x in args["depends_on"].split(",")]
                    kwargs["depends_on"] = deps
                except ValueError:
                    return _error_result(
                        "depends_on must be comma-separated integers (e.g. '1,2,3')"
                    )

            task = create_task(hc_home, team, **kwargs)
            return _json_result(task)
        except Exception as e:
            logger.exception("task_create failed")
            return _error_result(str(e))

    @tool(
        "task_list",
        "List tasks for the team, optionally filtered by status or assignee.",
        {
            "status": str,
            "assignee": str,
        },
    )
    async def task_list(args: dict) -> dict:
        try:
            from delegate.task import list_tasks

            kwargs: dict[str, Any] = {}
            if args.get("status"):
                kwargs["status"] = args["status"]
            if args.get("assignee"):
                kwargs["assignee"] = args["assignee"]

            tasks = list_tasks(hc_home, team, **kwargs)
            return _json_result(tasks)
        except Exception as e:
            logger.exception("task_list failed")
            return _error_result(str(e))

    @tool(
        "task_show",
        "Show detailed information about a specific task.",
        {"task_id": int},
    )
    async def task_show(args: dict) -> dict:
        try:
            from delegate.task import get_task

            task = get_task(hc_home, team, args["task_id"])
            return _json_result(task)
        except Exception as e:
            logger.exception("task_show failed")
            return _error_result(str(e))

    @tool(
        "task_assign",
        "Assign a task to a team member.",
        {"task_id": int, "assignee": str},
    )
    async def task_assign(args: dict) -> dict:
        try:
            from delegate.task import update_task

            update_task(
                hc_home, team, args["task_id"],
                assignee=args["assignee"],
            )
            return _text_result(
                f"Task T{args['task_id']:04d} assigned to {args['assignee']}"
            )
        except Exception as e:
            logger.exception("task_assign failed")
            return _error_result(str(e))

    @tool(
        "task_status",
        "Change the status of a task (e.g. 'in_progress', 'in_review', 'done').",
        {"task_id": int, "new_status": str},
    )
    async def task_status(args: dict) -> dict:
        try:
            from delegate.task import change_status

            change_status(hc_home, team, args["task_id"], args["new_status"])
            return _text_result(
                f"Task T{args['task_id']:04d} status changed to {args['new_status']}"
            )
        except Exception as e:
            logger.exception("task_status failed")
            return _error_result(str(e))

    @tool(
        "task_comment",
        "Add a durable comment/note to a task (specs, findings, decisions).",
        {"task_id": int, "body": str},
    )
    async def task_comment(args: dict) -> dict:
        try:
            from delegate.task import add_comment

            add_comment(
                hc_home, team, args["task_id"],
                author=agent,  # baked-in identity
                body=args["body"],
            )
            return _text_result(
                f"Comment added to T{args['task_id']:04d}"
            )
        except Exception as e:
            logger.exception("task_comment failed")
            return _error_result(str(e))

    @tool(
        "task_cancel",
        "Cancel a task (manager only — cleans up worktrees and branches).",
        {"task_id": int},
    )
    async def task_cancel(args: dict) -> dict:
        try:
            from delegate.task import cancel_task

            cancel_task(hc_home, team, args["task_id"])
            return _text_result(f"Task T{args['task_id']:04d} cancelled")
        except Exception as e:
            logger.exception("task_cancel failed")
            return _error_result(str(e))

    @tool(
        "task_attach",
        "Attach a file to a task.",
        {"task_id": int, "file_path": str},
    )
    async def task_attach(args: dict) -> dict:
        try:
            from delegate.task import update_task, get_task

            task = get_task(hc_home, team, args["task_id"])
            attachments = list(task.get("attachments", []))
            if args["file_path"] not in attachments:
                attachments.append(args["file_path"])
            update_task(hc_home, team, args["task_id"], attachments=attachments)
            return _text_result(
                f"Attached {args['file_path']} to T{args['task_id']:04d}"
            )
        except Exception as e:
            logger.exception("task_attach failed")
            return _error_result(str(e))

    @tool(
        "task_detach",
        "Remove a file attachment from a task.",
        {"task_id": int, "file_path": str},
    )
    async def task_detach(args: dict) -> dict:
        try:
            from delegate.task import update_task, get_task

            task = get_task(hc_home, team, args["task_id"])
            attachments = list(task.get("attachments", []))
            if args["file_path"] in attachments:
                attachments.remove(args["file_path"])
            update_task(hc_home, team, args["task_id"], attachments=attachments)
            return _text_result(
                f"Detached {args['file_path']} from T{args['task_id']:04d}"
            )
        except Exception as e:
            logger.exception("task_detach failed")
            return _error_result(str(e))

    # -----------------------------------------------------------------------
    # Repo tools
    # -----------------------------------------------------------------------

    @tool(
        "repo_list",
        "List all registered repositories for the team.",
        {},
    )
    async def repo_list(args: dict) -> dict:
        try:
            from delegate.repo import list_repos

            repos = list_repos(hc_home, team)
            if not repos:
                return _text_result("No repositories registered.")
            return _json_result(repos)
        except Exception as e:
            logger.exception("repo_list failed")
            return _error_result(str(e))

    # -----------------------------------------------------------------------
    # Git tools
    # -----------------------------------------------------------------------

    @tool(
        "rebase_to_main",
        "Rebase the current task branch onto latest main. Performs git reset "
        "--soft main, updates the task's base_sha to the new main HEAD. Does "
        "NOT auto-commit -- you must stage and commit changes yourself after "
        "resolving any conflicts. Fails if the working tree is dirty.",
        {"task_id": int},
    )
    async def rebase_to_main(args: dict) -> dict:
        try:
            import subprocess
            from delegate.task import get_task, update_task, format_task_id
            from delegate.repo import get_task_worktree_path, get_repo_path

            task_id = args["task_id"]
            task = get_task(hc_home, team, task_id)

            branch = task.get("branch")
            if not branch:
                return _error_result(f"Task {format_task_id(task_id)} has no branch")

            repos = task.get("repo", [])
            if not repos:
                return _error_result(f"Task {format_task_id(task_id)} has no repos")

            result_data = {
                "task_id": task_id,
                "branch": branch,
                "repos": {},
            }

            for repo_name in repos:
                # Get paths
                worktree_path = get_task_worktree_path(hc_home, team, repo_name, task_id)
                if not worktree_path.exists():
                    return _error_result(
                        f"Worktree not found for {repo_name}: {worktree_path}"
                    )

                repo_path = get_repo_path(hc_home, team, repo_name)
                wt_str = str(worktree_path)

                # Check for uncommitted changes
                diff_check = subprocess.run(
                    ["git", "diff", "--name-only", "HEAD"],
                    cwd=wt_str,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if diff_check.stdout.strip():
                    return _error_result(
                        f"Working tree is dirty in {repo_name}. "
                        f"Commit or stash changes before rebasing."
                    )

                # Check for staged changes
                staged_check = subprocess.run(
                    ["git", "diff", "--cached", "--name-only"],
                    cwd=wt_str,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if staged_check.stdout.strip():
                    return _error_result(
                        f"Working tree has staged changes in {repo_name}. "
                        f"Commit or unstage changes before rebasing."
                    )

                # Get current main HEAD
                main_sha_result = subprocess.run(
                    ["git", "rev-parse", "main"],
                    cwd=wt_str,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if main_sha_result.returncode != 0:
                    return _error_result(
                        f"Failed to get main HEAD in {repo_name}: "
                        f"{main_sha_result.stderr}"
                    )

                new_main_sha = main_sha_result.stdout.strip()

                # Perform git reset --soft main
                reset_result = subprocess.run(
                    ["git", "reset", "--soft", "main"],
                    cwd=wt_str,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if reset_result.returncode != 0:
                    return _error_result(
                        f"git reset --soft main failed in {repo_name}: "
                        f"{reset_result.stderr}"
                    )

                result_data["repos"][repo_name] = {
                    "new_base_sha": new_main_sha,
                    "status": "reset_complete",
                }

            # Update task base_sha for all repos
            base_sha_dict = {
                repo_name: data["new_base_sha"]
                for repo_name, data in result_data["repos"].items()
            }
            update_task(hc_home, team, task_id, base_sha=base_sha_dict)

            result_data["message"] = (
                f"Successfully reset {format_task_id(task_id)} to main. "
                f"Changes are staged. Review with 'git status' and commit when ready."
            )

            return _json_result(result_data)

        except Exception as e:
            logger.exception("rebase_to_main failed")
            return _error_result(str(e))

    return [
        mailbox_send,
        mailbox_inbox,
        task_create,
        task_list,
        task_show,
        task_assign,
        task_status,
        task_comment,
        task_cancel,
        task_attach,
        task_detach,
        repo_list,
        rebase_to_main,
    ]


def create_agent_mcp_server(hc_home: Path, team: str, agent: str):
    """Create an MCP server with all agent tools wired to the given context.

    Returns an MCP server object ready for ``Telephone(mcp_servers={...})``,
    or ``None`` if the SDK is not available (e.g. in test environments).
    """
    try:
        from claude_agent_sdk import create_sdk_mcp_server
    except ImportError:
        logger.debug("claude_agent_sdk not available — skipping MCP server creation")
        return None

    tools = build_agent_tools(hc_home, team, agent)
    return create_sdk_mcp_server("delegate", tools=tools)
