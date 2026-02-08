"""Simulated director for eval runs — answers manager questions from task specs.

The sim-director replaces the human director during automated eval runs.
It watches the director's inbox for messages from the manager, then responds
based strictly on the benchmark task spec (no volunteering extra info).

Uses claude_code_sdk.query() for one-shot LLM calls with a standardized prompt.

Usage:
    # Respond to a single message
    python -m scripts.sim_director respond <root> --message "..." --task-spec "..."

    # Run the polling loop
    python -m scripts.sim_director run <root> --specs-dir benchmarks/tasks/ [--poll-interval 2.0]
"""

import argparse
import asyncio
import logging
import threading
from pathlib import Path

import yaml

from scripts.mailbox import read_inbox, mark_inbox_read, send as mailbox_send

logger = logging.getLogger(__name__)

# The standardized prompt template for the sim-director.
SIM_DIRECTOR_PROMPT = """\
You are a director. Here is the task spec: {spec}. Answer the manager's question \
based only on this spec. Be concise."""


def _build_prompt(task_spec: str, message: str) -> str:
    """Build the full prompt for the LLM, combining the system template and message."""
    system = SIM_DIRECTOR_PROMPT.format(spec=task_spec)
    return f"{system}\n\nManager's message:\n{message}"


async def _query_llm(prompt: str, llm_query=None) -> str:
    """Call the LLM and return the text response.

    *llm_query* can be injected for testing. If None, uses claude_code_sdk.query.
    """
    if llm_query is not None:
        return await llm_query(prompt)

    from claude_code_sdk import query, ClaudeCodeOptions

    options = ClaudeCodeOptions(
        system_prompt="You are a simulated director for automated evaluation runs.",
        max_turns=1,
    )
    response_text = []
    async for msg in query(prompt=prompt, options=options):
        # Collect text blocks from assistant messages
        if hasattr(msg, "content"):
            for block in msg.content:
                if hasattr(block, "text"):
                    response_text.append(block.text)

    return "\n".join(response_text).strip() or "(no response)"


async def sim_director_respond(
    root: Path,
    task_spec: str,
    message: str,
    llm_query=None,
) -> str:
    """Given a message, return the sim-director's response.

    Args:
        root: Team root directory.
        task_spec: The full benchmark task spec text to ground the response.
        message: The manager's question or message.
        llm_query: Optional callable for testing (async func(prompt) -> str).

    Returns:
        The sim-director's response text.
    """
    prompt = _build_prompt(task_spec, message)
    return await _query_llm(prompt, llm_query=llm_query)


def _match_task_spec(message_body: str, task_specs: dict[str, str]) -> str | None:
    """Match a message to a task spec by finding the best matching task title.

    Looks for task titles mentioned in the message body. If none match,
    concatenates all specs as context (the director should know about all tasks).

    Args:
        message_body: The message text from the manager.
        task_specs: Dict of {task_title: task_description}.

    Returns:
        The matched task spec text, or a combined spec if no specific match.
    """
    # Try to find a specific task title mentioned in the message
    for title, description in task_specs.items():
        if title.lower() in message_body.lower():
            return f"Title: {title}\n\n{description}"

    # No specific match — provide all specs as context
    if task_specs:
        parts = []
        for title, description in task_specs.items():
            parts.append(f"## {title}\n{description}")
        return "\n\n---\n\n".join(parts)

    return None


def _get_director_name(root: Path) -> str:
    """Get the director's name from the team roster."""
    from scripts.bootstrap import get_member_by_role
    return get_member_by_role(root, "director") or "director"


async def _process_inbox(
    root: Path,
    task_specs: dict[str, str],
    director_name: str,
    llm_query=None,
) -> int:
    """Process all unread messages in the director's inbox.

    Returns the number of messages processed.
    """
    try:
        messages = read_inbox(root, director_name, unread_only=True)
    except ValueError:
        # Director agent dir doesn't exist yet
        return 0

    processed = 0
    for msg in messages:
        logger.info(
            "Sim-director received message from %s: %.80s",
            msg.sender, msg.body,
        )

        # Match the message to a task spec
        spec = _match_task_spec(msg.body, task_specs)
        if spec is None:
            response = "I don't have any task specs to reference. Please provide more context."
        else:
            response = await sim_director_respond(
                root, spec, msg.body, llm_query=llm_query,
            )

        # Send the response back to the sender
        mailbox_send(root, director_name, msg.sender, response)
        logger.info(
            "Sim-director responded to %s: %.80s",
            msg.sender, response,
        )

        # Mark the message as read
        if msg.filename:
            mark_inbox_read(root, director_name, msg.filename)

        processed += 1

    return processed


async def run_sim_director(
    root: Path,
    task_specs: dict[str, str],
    poll_interval: float = 2.0,
    stop_event: threading.Event | asyncio.Event | None = None,
    llm_query=None,
) -> None:
    """Poll director inbox, match messages to task specs, respond, loop until stopped.

    Args:
        root: Team root directory.
        task_specs: Dict of {task_title: task_description} from benchmark YAML files.
        poll_interval: Seconds between inbox checks.
        stop_event: Set this event to stop the loop. Accepts either
            threading.Event (thread-safe, for cross-thread use) or
            asyncio.Event (for single-loop use). If None, creates a
            threading.Event internally.
        llm_query: Optional callable for testing (async func(prompt) -> str).
    """
    if stop_event is None:
        stop_event = threading.Event()

    director_name = _get_director_name(root)
    logger.info(
        "Sim-director starting for %s with %d task specs, polling every %.1fs",
        director_name, len(task_specs), poll_interval,
    )

    while not stop_event.is_set():
        try:
            processed = await _process_inbox(
                root, task_specs, director_name, llm_query=llm_query,
            )
            if processed > 0:
                logger.info("Sim-director processed %d messages", processed)
        except Exception:
            logger.exception("Error in sim-director polling loop")

        # Wait for poll_interval or until stopped.
        # threading.Event.wait() is used for thread-safe cross-thread signaling.
        # asyncio.Event uses asyncio.wait_for for single-loop callers.
        if isinstance(stop_event, threading.Event):
            stop_event.wait(timeout=poll_interval)
        else:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
                break
            except asyncio.TimeoutError:
                pass

    logger.info("Sim-director stopped")


def start_sim_director_thread(
    root: Path,
    task_specs: dict[str, str],
    poll_interval: float = 2.0,
    llm_query=None,
) -> tuple[threading.Thread, threading.Event]:
    """Start the sim-director in a background thread.

    Returns (thread, stop_event). Call stop_event.set() to stop the loop.

    Uses threading.Event (not asyncio.Event) for thread-safe signaling
    between the main thread and the sim-director's event loop.

    This is convenient for the eval runner (T0031) which needs to run
    the sim-director alongside the daemon in the same process.
    """
    stop_event = threading.Event()

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                run_sim_director(
                    root, task_specs,
                    poll_interval=poll_interval,
                    stop_event=stop_event,
                    llm_query=llm_query,
                )
            )
        finally:
            loop.close()

    thread = threading.Thread(target=_run, daemon=True, name="sim-director")
    thread.start()
    return thread, stop_event


def load_task_specs_from_dir(specs_dir: Path) -> dict[str, str]:
    """Load benchmark task specs from a directory of YAML files.

    Args:
        specs_dir: Directory containing benchmark task YAML files.

    Returns:
        Dict of {task_title: task_description}.
    """
    task_specs: dict[str, str] = {}
    if not specs_dir.is_dir():
        logger.warning("Specs directory not found: %s", specs_dir)
        return task_specs

    for yaml_file in sorted(specs_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text())
            if data and "title" in data and "description" in data:
                task_specs[data["title"]] = data["description"]
                logger.info("Loaded task spec: %s", data["title"])
        except Exception:
            logger.exception("Failed to load spec from %s", yaml_file)

    return task_specs


def main():
    parser = argparse.ArgumentParser(description="Simulated director for eval runs")
    sub = parser.add_subparsers(dest="command", required=True)

    # respond — single message
    p_respond = sub.add_parser("respond", help="Respond to a single message")
    p_respond.add_argument("root", type=Path, help="Team root directory")
    p_respond.add_argument("--message", required=True, help="The message to respond to")
    p_respond.add_argument("--task-spec", required=True, help="Task spec text")

    # run — polling loop
    p_run = sub.add_parser("run", help="Run the polling loop")
    p_run.add_argument("root", type=Path, help="Team root directory")
    p_run.add_argument(
        "--specs-dir", type=Path, required=True,
        help="Directory containing benchmark task YAML files",
    )
    p_run.add_argument(
        "--poll-interval", type=float, default=2.0,
        help="Seconds between inbox checks (default 2.0)",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.command == "respond":
        response = asyncio.run(
            sim_director_respond(Path(args.root), args.task_spec, args.message)
        )
        print(response)

    elif args.command == "run":
        task_specs = load_task_specs_from_dir(args.specs_dir)
        if not task_specs:
            print("No task specs found. Exiting.")
            return
        print(f"Loaded {len(task_specs)} task specs. Starting sim-director...")
        asyncio.run(
            run_sim_director(
                Path(args.root), task_specs,
                poll_interval=args.poll_interval,
            )
        )


if __name__ == "__main__":
    main()
