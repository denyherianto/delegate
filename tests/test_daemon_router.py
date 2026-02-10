"""Tests for delegate/router.py — the daemon's message routing logic."""

import pytest

from delegate.mailbox import send, read_inbox, read_outbox, Message, deliver
from delegate.chat import get_messages
from delegate.router import route_once, BossQueue

TEAM = "testteam"


class TestRouteOnce:
    def test_route_single_message(self, tmp_team):
        """A message in alice's outbox is delivered to bob's inbox."""
        send(tmp_team, TEAM, "alice", "bob", "Hello Bob!")
        routed = route_once(tmp_team, TEAM)
        assert routed == 1

        inbox = read_inbox(tmp_team, TEAM, "bob", unread_only=True)
        assert len(inbox) == 1
        assert inbox[0].sender == "alice"
        assert inbox[0].body == "Hello Bob!"

    def test_route_preserves_content(self, tmp_team):
        """Routed message content matches exactly."""
        original = "Line 1\nLine 2\n🌍 Special chars: \"quotes\", commas"
        send(tmp_team, TEAM, "alice", "bob", original)
        route_once(tmp_team, TEAM)

        inbox = read_inbox(tmp_team, TEAM, "bob")
        assert inbox[0].body == original

    def test_route_advances_outbox(self, tmp_team):
        """After routing, the message moves from outbox/new to outbox/cur."""
        send(tmp_team, TEAM, "alice", "bob", "Hello")
        assert len(read_outbox(tmp_team, TEAM, "alice", pending_only=True)) == 1

        route_once(tmp_team, TEAM)

        assert len(read_outbox(tmp_team, TEAM, "alice", pending_only=True)) == 0
        assert len(read_outbox(tmp_team, TEAM, "alice", pending_only=False)) == 1

    def test_route_skips_already_routed(self, tmp_team):
        """Running route twice with no new messages doesn't create duplicates."""
        send(tmp_team, TEAM, "alice", "bob", "Hello")
        route_once(tmp_team, TEAM)
        route_once(tmp_team, TEAM)  # second cycle, nothing new

        inbox = read_inbox(tmp_team, TEAM, "bob", unread_only=True)
        assert len(inbox) == 1

    def test_route_multiple_senders(self, tmp_team):
        """Messages from multiple agents in the same cycle all get delivered."""
        send(tmp_team, TEAM, "alice", "bob", "From Alice")
        send(tmp_team, TEAM, "manager", "bob", "From Manager")
        routed = route_once(tmp_team, TEAM)
        assert routed == 2

        inbox = read_inbox(tmp_team, TEAM, "bob")
        assert len(inbox) == 2
        senders = {m.sender for m in inbox}
        assert senders == {"alice", "manager"}

    def test_route_logs_to_sqlite(self, tmp_team):
        """Every routed message is also logged in the SQLite messages table."""
        send(tmp_team, TEAM, "alice", "bob", "Logged message")
        route_once(tmp_team, TEAM)

        messages = get_messages(tmp_team, msg_type="chat")
        assert len(messages) == 1
        assert messages[0]["sender"] == "alice"
        assert messages[0]["recipient"] == "bob"
        assert messages[0]["content"] == "Logged message"

    def test_route_to_boss(self, tmp_team):
        """Messages to 'boss' are delivered to boss's inbox AND queued."""
        from delegate.config import get_boss
        boss_name = get_boss(tmp_team) or "nikhil"
        dq = BossQueue()
        send(tmp_team, TEAM, "manager", boss_name, "Question for boss")
        routed = route_once(tmp_team, TEAM, boss_queue=dq, boss_name=boss_name)

        assert routed == 1

        # Delivered to boss's inbox
        inbox = read_inbox(tmp_team, TEAM, boss_name, unread_only=True)
        assert len(inbox) == 1
        assert inbox[0].body == "Question for boss"

        # Also pushed to BossQueue for web UI
        assert len(dq.peek()) == 1
        assert dq.peek()[0].body == "Question for boss"

    def test_route_from_boss(self, tmp_team):
        """Boss's outbox is scanned like any other agent."""
        from delegate.config import get_boss
        boss_name = get_boss(tmp_team) or "nikhil"
        send(tmp_team, TEAM, boss_name, "manager", "Start the project")
        routed = route_once(tmp_team, TEAM, boss_name=boss_name)
        assert routed == 1

        inbox = read_inbox(tmp_team, TEAM, "manager", unread_only=True)
        assert len(inbox) == 1
        assert inbox[0].sender == boss_name
        assert inbox[0].body == "Start the project"

    def test_route_empty_outboxes(self, tmp_team):
        """Route with no pending messages returns 0."""
        routed = route_once(tmp_team, TEAM)
        assert routed == 0

    def test_bidirectional_conversation(self, tmp_team):
        """Simulate a back-and-forth between two agents."""
        send(tmp_team, TEAM, "alice", "bob", "Hey Bob")
        route_once(tmp_team, TEAM)

        send(tmp_team, TEAM, "bob", "alice", "Hey Alice")
        route_once(tmp_team, TEAM)

        alice_inbox = read_inbox(tmp_team, TEAM, "alice")
        bob_inbox = read_inbox(tmp_team, TEAM, "bob")
        assert len(alice_inbox) == 1
        assert alice_inbox[0].sender == "bob"
        assert len(bob_inbox) == 1
        assert bob_inbox[0].sender == "alice"

        # Both should be in SQLite
        all_msgs = get_messages(tmp_team, msg_type="chat")
        assert len(all_msgs) == 2


class TestBossQueue:
    def test_put_and_get(self):
        dq = BossQueue()
        msg = Message(sender="mgr", recipient="boss", time="t", body="Hi")
        dq.put(msg)
        msgs = dq.get_all()
        assert len(msgs) == 1
        assert msgs[0].body == "Hi"
        # get_all clears the queue
        assert len(dq.get_all()) == 0

    def test_peek_does_not_consume(self):
        dq = BossQueue()
        msg = Message(sender="mgr", recipient="boss", time="t", body="Hi")
        dq.put(msg)
        assert len(dq.peek()) == 1
        assert len(dq.peek()) == 1  # still there
