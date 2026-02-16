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
            "recipient": str,
            "message": str,
            "task_id": int,
        },
    )
    async def mailbox_send(args: dict) -> dict:
        try:
            from delegate.mailbox import send

            recipient = args["recipient"]
            message = args["message"]
            task_id = args.get("task_id")

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
