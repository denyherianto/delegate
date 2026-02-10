"""Daemon message router — lightweight routing cycle for the daemon loop.

With the SQLite-backed mailbox, ``send()`` delivers messages immediately.
The router's remaining job is to notify the in-memory BossQueue so the
web UI can push real-time updates when a message arrives for the boss.

The actual event loop is in delegate/daemon.py.
"""

import logging
from pathlib import Path

from delegate.mailbox import Message, read_inbox

logger = logging.getLogger(__name__)


class BossQueue:
    """In-memory queue for messages addressed to the boss."""

    def __init__(self):
        self.messages: list[Message] = []
        self._seen_ids: set[int] = set()

    def put(self, msg: Message) -> None:
        if msg.id is not None and msg.id not in self._seen_ids:
            self.messages.append(msg)
            self._seen_ids.add(msg.id)

    def get_all(self) -> list[Message]:
        msgs = list(self.messages)
        self.messages.clear()
        return msgs

    def peek(self) -> list[Message]:
        return list(self.messages)


def route_once(
    hc_home: Path,
    team: str,
    boss_queue: BossQueue | None = None,
    boss_name: str | None = None,
) -> int:
    """Run one routing cycle.

    With immediate delivery in ``send()``, the only remaining work is to
    check for new unread messages addressed to the boss and push them to
    the BossQueue for web UI notifications.

    Returns the number of new boss messages found in this cycle.
    """
    if boss_name is None:
        from delegate.config import get_boss
        boss_name = get_boss(hc_home)

    if not boss_name or boss_queue is None:
        return 0

    # Check for unread messages addressed to the boss
    unread = read_inbox(hc_home, team, boss_name, unread_only=True)
    notified = 0
    for msg in unread:
        boss_queue.put(msg)
        notified += 1

    if notified > 0:
        logger.debug(
            "Boss notification cycle | team=%s | new_messages=%d",
            team, notified,
        )

    return notified
