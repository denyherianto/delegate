"""Maildir-based mailbox system for agent communication.

Each agent has an inbox/ and outbox/ with Maildir-style subbossies:
    new/  — unprocessed messages
    cur/  — processed messages
    tmp/  — in-flight writes (atomicity)

Message file format:
    sender: <name>
    recipient: <name>
    time: <ISO 8601>
    ---
    <message body>

Usage:
    python -m boss.mailbox send <home> <team> <sender> <recipient> <message>
    python -m boss.mailbox inbox <home> <team> <agent> [--unread]
    python -m boss.mailbox outbox <home> <team> <agent> [--pending]
"""

import argparse
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from boss.paths import agent_dir as _resolve_agent_dir


@dataclass
class Message:
    sender: str
    recipient: str
    time: str
    body: str
    filename: str | None = None

    def serialize(self) -> str:
        """Serialize message to the file format."""
        return f"sender: {self.sender}\nrecipient: {self.recipient}\ntime: {self.time}\n---\n{self.body}"

    @classmethod
    def deserialize(cls, text: str, filename: str | None = None) -> "Message":
        """Parse a message file's text content."""
        header, _, body = text.partition("\n---\n")
        fields = {}
        for line in header.strip().splitlines():
            key, _, value = line.partition(": ")
            fields[key.strip()] = value.strip()
        return cls(
            sender=fields["sender"],
            recipient=fields["recipient"],
            time=fields["time"],
            body=body,
            filename=filename,
        )


def _agent_dir(hc_home: Path, team: str, agent: str) -> Path:
    """Return the mailbox directory for an agent (or the boss).

    If *agent* matches the org-wide boss name, the global boss
    mailbox at ``~/.boss/boss/`` is returned instead of a
    team-scoped agent directory.
    """
    from boss.config import get_boss
    from boss.paths import boss_person_dir as _boss_person_dir

    boss = get_boss(hc_home)
    if boss and agent == boss:
        dd = _boss_person_dir(hc_home)
        if not dd.is_dir():
            raise ValueError(f"Boss '{agent}' mailbox not found at {dd}")
        return dd

    d = _resolve_agent_dir(hc_home, team, agent)
    if not d.is_dir():
        raise ValueError(f"Agent '{agent}' not found at {d}")
    return d


def _unique_filename() -> str:
    """Generate a unique filename for a message (Maildir convention)."""
    timestamp = int(time.time() * 1_000_000)
    unique = uuid.uuid4().hex[:8]
    pid = os.getpid()
    return f"{timestamp}.{pid}.{unique}"


def _write_atomic(directory: Path, content: str) -> str:
    """Write content to a file atomically using Maildir tmp->new pattern.

    Returns the filename of the written message.
    """
    filename = _unique_filename()
    tmp_path = directory.parent / "tmp" / filename
    new_path = directory / filename

    # Write to tmp first
    tmp_path.write_text(content)
    # Atomic rename to new
    tmp_path.rename(new_path)

    return filename


def send(hc_home: Path, team: str, sender: str, recipient: str, message: str) -> str:
    """Send a message by writing it to the sender's outbox/new/.

    The daemon router will pick it up, deliver it to the recipient's inbox,
    and log it to the chat database.

    Returns the filename of the written message.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    msg = Message(sender=sender, recipient=recipient, time=now, body=message)

    ad = _agent_dir(hc_home, team, sender)
    outbox_new = ad / "outbox" / "new"
    return _write_atomic(outbox_new, msg.serialize())


def read_inbox(hc_home: Path, team: str, agent: str, unread_only: bool = True) -> list[Message]:
    """Read messages from an agent's inbox.

    If unread_only=True, only reads from new/.
    If unread_only=False, reads from both new/ and cur/.
    """
    ad = _agent_dir(hc_home, team, agent)
    messages = []

    dirs = [ad / "inbox" / "new"]
    if not unread_only:
        dirs.append(ad / "inbox" / "cur")

    for d in dirs:
        for f in sorted(d.iterdir()):
            if f.is_file():
                msg = Message.deserialize(f.read_text(), filename=f.name)
                messages.append(msg)

    return messages


def read_outbox(hc_home: Path, team: str, agent: str, pending_only: bool = True) -> list[Message]:
    """Read messages from an agent's outbox.

    If pending_only=True, only reads from new/ (not yet routed).
    If pending_only=False, reads from both new/ and cur/.
    """
    ad = _agent_dir(hc_home, team, agent)
    messages = []

    dirs = [ad / "outbox" / "new"]
    if not pending_only:
        dirs.append(ad / "outbox" / "cur")

    for d in dirs:
        for f in sorted(d.iterdir()):
            if f.is_file():
                msg = Message.deserialize(f.read_text(), filename=f.name)
                messages.append(msg)

    return messages


def mark_inbox_read(hc_home: Path, team: str, agent: str, filename: str) -> None:
    """Move a message from inbox/new/ to inbox/cur/."""
    ad = _agent_dir(hc_home, team, agent)
    src = ad / "inbox" / "new" / filename
    dst = ad / "inbox" / "cur" / filename
    if not src.exists():
        raise FileNotFoundError(f"Inbox message not found: {src}")
    src.rename(dst)


def mark_outbox_routed(hc_home: Path, team: str, agent: str, filename: str) -> None:
    """Move a message from outbox/new/ to outbox/cur/."""
    ad = _agent_dir(hc_home, team, agent)
    src = ad / "outbox" / "new" / filename
    dst = ad / "outbox" / "cur" / filename
    if not src.exists():
        raise FileNotFoundError(f"Outbox message not found: {src}")
    src.rename(dst)


def deliver(hc_home: Path, team: str, message: Message) -> str:
    """Deliver a message to the recipient's inbox/new/.

    Returns the filename of the delivered message.
    """
    ad = _agent_dir(hc_home, team, message.recipient)
    inbox_new = ad / "inbox" / "new"
    return _write_atomic(inbox_new, message.serialize())


def main():
    parser = argparse.ArgumentParser(description="Mailbox management")
    sub = parser.add_subparsers(dest="command", required=True)

    # send
    p_send = sub.add_parser("send", help="Send a message")
    p_send.add_argument("home", type=Path)
    p_send.add_argument("team")
    p_send.add_argument("sender", help="Sending agent name")
    p_send.add_argument("recipient", help="Recipient agent name")
    p_send.add_argument("message", help="Message body")

    # inbox
    p_inbox = sub.add_parser("inbox", help="Read inbox")
    p_inbox.add_argument("home", type=Path)
    p_inbox.add_argument("team")
    p_inbox.add_argument("agent", help="Agent name")
    p_inbox.add_argument("--all", action="store_true", help="Include read messages")

    # outbox
    p_outbox = sub.add_parser("outbox", help="Read outbox")
    p_outbox.add_argument("home", type=Path)
    p_outbox.add_argument("team")
    p_outbox.add_argument("agent", help="Agent name")
    p_outbox.add_argument("--all", action="store_true", help="Include routed messages")

    args = parser.parse_args()

    if args.command == "send":
        fname = send(args.home, args.team, args.sender, args.recipient, args.message)
        print(f"Message sent: {fname}")

    elif args.command == "inbox":
        messages = read_inbox(args.home, args.team, args.agent, unread_only=not args.all)
        for msg in messages:
            print(f"[{msg.time}] {msg.sender}: {msg.body}")
        if not messages:
            print("(no messages)")

    elif args.command == "outbox":
        messages = read_outbox(args.home, args.team, args.agent, pending_only=not args.all)
        for msg in messages:
            print(f"[{msg.time}] -> {msg.recipient}: {msg.body}")
        if not messages:
            print("(no messages)")


if __name__ == "__main__":
    main()
