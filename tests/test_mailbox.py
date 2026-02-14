"""Tests for delegate/mailbox.py — SQLite-backed message system."""

import pytest

from delegate.mailbox import (
    Message,
    send,
    read_inbox,
    read_outbox,
    mark_seen,
    mark_seen_batch,
    mark_processed,
    mark_processed_batch,
    deliver,
    has_unread,
    count_unread,
    agents_with_unread,
    recent_processed,
    recent_conversation,
)

TEAM = "testteam"


class TestMessageSerialization:
    def test_round_trip(self):
        msg = Message(
            sender="alice",
            recipient="bob",
            time="2026-02-08T12:00:00.000000Z",
            body="Hello Bob!",
        )
        text = msg.serialize()
        parsed = Message.deserialize(text)
        assert parsed.sender == "alice"
        assert parsed.recipient == "bob"
        assert parsed.time == "2026-02-08T12:00:00.000000Z"
        assert parsed.body == "Hello Bob!"

    def test_multiline_body(self):
        body = "Line 1\nLine 2\nLine 3"
        msg = Message(
            sender="alice",
            recipient="bob",
            time="2026-02-08T12:00:00.000000Z",
            body=body,
        )
        parsed = Message.deserialize(msg.serialize())
        assert parsed.body == body

    def test_special_characters_in_body(self):
        body = 'He said "hello, world!" — and then: done.'
        msg = Message(
            sender="alice",
            recipient="bob",
            time="2026-02-08T12:00:00.000000Z",
            body=body,
        )
        parsed = Message.deserialize(msg.serialize())
        assert parsed.body == body


class TestSend:
    def test_send_returns_id(self, tmp_team):
        msg_id = send(tmp_team, TEAM, "alice", "bob", "Hello")
        assert isinstance(msg_id, int) and msg_id > 0

    def test_send_delivers_immediately(self, tmp_team):
        """Messages are delivered on send — visible in recipient inbox."""
        send(tmp_team, TEAM, "alice", "bob", "Hello Bob!")
        inbox = read_inbox(tmp_team, TEAM, "bob", unread_only=True)
        assert len(inbox) == 1
        assert inbox[0].sender == "alice"
        assert inbox[0].body == "Hello Bob!"
        assert inbox[0].delivered_at is not None

    def test_send_multiple_messages(self, tmp_team):
        id1 = send(tmp_team, TEAM, "alice", "bob", "First")
        id2 = send(tmp_team, TEAM, "alice", "bob", "Second")
        assert id1 != id2
        inbox = read_inbox(tmp_team, TEAM, "bob")
        assert len(inbox) == 2

    def test_send_logs_to_chat(self, tmp_team):
        """send() also writes to the chat messages table."""
        from delegate.chat import get_messages
        send(tmp_team, TEAM, "alice", "bob", "Logged msg")
        msgs = get_messages(tmp_team, TEAM, msg_type="chat")
        assert len(msgs) == 1
        assert msgs[0]["sender"] == "alice"


class TestReadInbox:
    def test_read_inbox_empty(self, tmp_team):
        messages = read_inbox(tmp_team, TEAM, "bob")
        assert messages == []

    def test_read_inbox_returns_delivered_messages(self, tmp_team):
        send(tmp_team, TEAM, "alice", "bob", "Hello!")
        messages = read_inbox(tmp_team, TEAM, "bob")
        assert len(messages) == 1
        assert messages[0].sender == "alice"
        assert messages[0].body == "Hello!"

    def test_read_inbox_unread_only(self, tmp_team):
        msg_id = send(tmp_team, TEAM, "alice", "bob", "Hello!")
        mark_processed(tmp_team, TEAM, msg_id)

        # Unread only should return nothing (message is processed)
        assert read_inbox(tmp_team, TEAM, "bob", unread_only=True) == []
        # All should return the message
        all_msgs = read_inbox(tmp_team, TEAM, "bob", unread_only=False)
        assert len(all_msgs) == 1


class TestReadOutbox:
    def test_read_outbox_sent(self, tmp_team):
        """With immediate delivery, sent messages appear in outbox (not pending)."""
        send(tmp_team, TEAM, "alice", "bob", "Hello")
        # Already delivered, so pending_only returns nothing
        pending = read_outbox(tmp_team, TEAM, "alice", pending_only=True)
        assert len(pending) == 0
        # All shows the message
        all_msgs = read_outbox(tmp_team, TEAM, "alice", pending_only=False)
        assert len(all_msgs) == 1
        assert all_msgs[0].body == "Hello"


class TestMarkProcessed:
    def test_mark_processed_removes_from_unread(self, tmp_team):
        msg_id = send(tmp_team, TEAM, "alice", "bob", "Hello!")
        assert len(read_inbox(tmp_team, TEAM, "bob", unread_only=True)) == 1

        mark_processed(tmp_team, TEAM, msg_id)
        assert len(read_inbox(tmp_team, TEAM, "bob", unread_only=True)) == 0
        # Message still exists when reading all
        all_msgs = read_inbox(tmp_team, TEAM, "bob", unread_only=False)
        assert len(all_msgs) == 1
        assert all_msgs[0].processed_at is not None


class TestSeenAndProcessed:
    """Test the seen_at / processed_at lifecycle columns."""

    def test_mark_seen(self, tmp_team):
        msg_id = send(tmp_team, TEAM, "alice", "bob", "Hello")
        mark_seen(tmp_team, TEAM, msg_id)

        inbox = read_inbox(tmp_team, TEAM, "bob")
        assert inbox[0].seen_at is not None
        assert inbox[0].processed_at is None

    def test_mark_seen_batch(self, tmp_team):
        id1 = send(tmp_team, TEAM, "alice", "bob", "First")
        id2 = send(tmp_team, TEAM, "alice", "bob", "Second")
        mark_seen_batch(tmp_team, TEAM, [id1, id2])

        inbox = read_inbox(tmp_team, TEAM, "bob")
        assert all(m.seen_at is not None for m in inbox)

    def test_mark_processed(self, tmp_team):
        msg_id = send(tmp_team, TEAM, "alice", "bob", "Hello")
        mark_seen(tmp_team, TEAM, msg_id)
        mark_processed(tmp_team, TEAM, msg_id)

        inbox = read_inbox(tmp_team, TEAM, "bob", unread_only=False)
        assert inbox[0].seen_at is not None
        assert inbox[0].processed_at is not None

    def test_mark_processed_batch(self, tmp_team):
        id1 = send(tmp_team, TEAM, "alice", "bob", "First")
        id2 = send(tmp_team, TEAM, "alice", "bob", "Second")
        mark_processed_batch(tmp_team, TEAM, [id1, id2])

        inbox = read_inbox(tmp_team, TEAM, "bob", unread_only=False)
        assert all(m.processed_at is not None for m in inbox)

    def test_full_lifecycle(self, tmp_team):
        """Message goes through delivered → seen → processed."""
        msg_id = send(tmp_team, TEAM, "alice", "bob", "Hello")

        msg = read_inbox(tmp_team, TEAM, "bob")[0]
        assert msg.delivered_at is not None
        assert msg.seen_at is None
        assert msg.processed_at is None

        mark_seen(tmp_team, TEAM, msg_id)
        msg = read_inbox(tmp_team, TEAM, "bob")[0]
        assert msg.seen_at is not None

        mark_processed(tmp_team, TEAM, msg_id)
        # processed = done, no longer unread
        assert read_inbox(tmp_team, TEAM, "bob", unread_only=True) == []
        msg = read_inbox(tmp_team, TEAM, "bob", unread_only=False)[0]
        assert msg.processed_at is not None


class TestDeliver:
    def test_deliver_to_recipient_inbox(self, tmp_team):
        msg = Message(
            sender="alice",
            recipient="bob",
            time="2026-02-08T12:00:00.000000Z",
            body="Delivered!",
        )
        msg_id = deliver(tmp_team, TEAM, msg)
        assert isinstance(msg_id, int) and msg_id > 0

        inbox = read_inbox(tmp_team, TEAM, "bob")
        assert len(inbox) == 1
        assert inbox[0].body == "Delivered!"


class TestHasUnread:
    def test_no_unread(self, tmp_team):
        assert not has_unread(tmp_team, TEAM, "bob")

    def test_has_unread(self, tmp_team):
        send(tmp_team, TEAM, "alice", "bob", "Hey")
        assert has_unread(tmp_team, TEAM, "bob")

    def test_no_unread_after_processed(self, tmp_team):
        msg_id = send(tmp_team, TEAM, "alice", "bob", "Hey")
        mark_processed(tmp_team, TEAM, msg_id)
        assert not has_unread(tmp_team, TEAM, "bob")


class TestCountUnread:
    def test_count_zero(self, tmp_team):
        assert count_unread(tmp_team, TEAM, "bob") == 0

    def test_count_matches(self, tmp_team):
        send(tmp_team, TEAM, "alice", "bob", "First")
        send(tmp_team, TEAM, "alice", "bob", "Second")
        assert count_unread(tmp_team, TEAM, "bob") == 2


class TestMessageEscaping:
    def test_commas_in_body(self, tmp_team):
        send(tmp_team, TEAM, "alice", "bob", "one, two, three")
        msgs = read_inbox(tmp_team, TEAM, "bob")
        assert msgs[0].body == "one, two, three"

    def test_quotes_in_body(self, tmp_team):
        send(tmp_team, TEAM, "alice", "bob", 'She said "hi"')
        msgs = read_inbox(tmp_team, TEAM, "bob")
        assert msgs[0].body == 'She said "hi"'

    def test_newlines_in_body(self, tmp_team):
        send(tmp_team, TEAM, "alice", "bob", "line1\nline2\nline3")
        msgs = read_inbox(tmp_team, TEAM, "bob")
        assert msgs[0].body == "line1\nline2\nline3"

    def test_unicode_in_body(self, tmp_team):
        send(tmp_team, TEAM, "alice", "bob", "Hello 🌍 — über cool")
        msgs = read_inbox(tmp_team, TEAM, "bob")
        assert msgs[0].body == "Hello 🌍 — über cool"


class TestTeamIsolation:
    """Test that team filters prevent cross-team message leakage.

    Each function that queries messages must include 'AND team = ?' to prevent
    messages from leaking across teams. We use different agent names per team
    since names must be globally unique, but test that the team filter still
    works correctly by ensuring queries only return results for the specified team.
    """

    def test_has_unread_team_isolation(self, tmp_team):
        """has_unread() should only return true for messages in the specified team."""
        from delegate.bootstrap import bootstrap

        # Create two additional teams (tmp_team fixture already creates "testteam")
        bootstrap(tmp_team, "alpha", manager="mgr-alpha", agents=["agent-alpha"])
        bootstrap(tmp_team, "beta", manager="mgr-beta", agents=["agent-beta"])

        # Send message to agent-alpha in team alpha
        send(tmp_team, "alpha", "mgr-alpha", "agent-alpha", "Alpha message")

        # agent-alpha should have unread in alpha
        assert has_unread(tmp_team, "alpha", "agent-alpha")
        # agent-beta in beta should not have unread
        assert not has_unread(tmp_team, "beta", "agent-beta")

    def test_count_unread_team_isolation(self, tmp_team):
        """count_unread() should only count messages in the specified team."""
        from delegate.bootstrap import bootstrap

        bootstrap(tmp_team, "alpha", manager="mgr-alpha", agents=["agent-alpha"])
        bootstrap(tmp_team, "beta", manager="mgr-beta", agents=["agent-beta"])

        # Send 2 messages to agent-alpha in alpha, 1 to agent-beta in beta
        send(tmp_team, "alpha", "mgr-alpha", "agent-alpha", "Alpha msg 1")
        send(tmp_team, "alpha", "mgr-alpha", "agent-alpha", "Alpha msg 2")
        send(tmp_team, "beta", "mgr-beta", "agent-beta", "Beta msg 1")

        # Counts should be isolated by team
        assert count_unread(tmp_team, "alpha", "agent-alpha") == 2
        assert count_unread(tmp_team, "beta", "agent-beta") == 1

    def test_agents_with_unread_team_isolation(self, tmp_team):
        """agents_with_unread() should only return agents with unread in the specified team."""
        from delegate.bootstrap import bootstrap

        bootstrap(tmp_team, "alpha", manager="mgr-alpha", agents=["agent-a1", "agent-a2"])
        bootstrap(tmp_team, "beta", manager="mgr-beta", agents=["agent-b1", "agent-b2"])

        # Send messages in alpha
        send(tmp_team, "alpha", "mgr-alpha", "agent-a1", "Alpha to a1")
        send(tmp_team, "alpha", "mgr-alpha", "agent-a2", "Alpha to a2")

        # Send message in beta
        send(tmp_team, "beta", "mgr-beta", "agent-b2", "Beta to b2")

        # Each team should only see its own agents
        alpha_agents = agents_with_unread(tmp_team, "alpha")
        beta_agents = agents_with_unread(tmp_team, "beta")

        assert set(alpha_agents) == {"agent-a1", "agent-a2"}
        assert set(beta_agents) == {"agent-b2"}

    def test_recent_processed_team_isolation(self, tmp_team):
        """recent_processed() should only return messages from the specified team."""
        from delegate.bootstrap import bootstrap

        bootstrap(tmp_team, "alpha", manager="mgr-alpha", agents=["agent-alpha"])
        bootstrap(tmp_team, "beta", manager="mgr-beta", agents=["agent-beta"])

        # Send and process messages in both teams
        alpha_id = send(tmp_team, "alpha", "mgr-alpha", "agent-alpha", "Alpha msg")
        beta_id = send(tmp_team, "beta", "mgr-beta", "agent-beta", "Beta msg")

        mark_processed(tmp_team, "alpha", alpha_id)
        mark_processed(tmp_team, "beta", beta_id)

        # Each team should only see its own processed messages
        alpha_msgs = recent_processed(tmp_team, "alpha", "agent-alpha")
        beta_msgs = recent_processed(tmp_team, "beta", "agent-beta")

        assert len(alpha_msgs) == 1
        assert alpha_msgs[0].body == "Alpha msg"

        assert len(beta_msgs) == 1
        assert beta_msgs[0].body == "Beta msg"

    def test_recent_processed_with_sender_team_isolation(self, tmp_team):
        """recent_processed() with from_sender should filter by team."""
        from delegate.bootstrap import bootstrap

        bootstrap(tmp_team, "alpha", manager="mgr-alpha", agents=["agent-alpha"])
        bootstrap(tmp_team, "beta", manager="mgr-beta", agents=["agent-beta"])

        # Send from managers to agents in both teams
        alpha_id = send(tmp_team, "alpha", "mgr-alpha", "agent-alpha", "Alpha from mgr")
        beta_id = send(tmp_team, "beta", "mgr-beta", "agent-beta", "Beta from mgr")

        mark_processed(tmp_team, "alpha", alpha_id)
        mark_processed(tmp_team, "beta", beta_id)

        # Filter by sender should still respect team boundaries
        alpha_msgs = recent_processed(tmp_team, "alpha", "agent-alpha", from_sender="mgr-alpha")
        beta_msgs = recent_processed(tmp_team, "beta", "agent-beta", from_sender="mgr-beta")

        assert len(alpha_msgs) == 1
        assert alpha_msgs[0].body == "Alpha from mgr"

        assert len(beta_msgs) == 1
        assert beta_msgs[0].body == "Beta from mgr"

    def test_recent_conversation_team_isolation(self, tmp_team):
        """recent_conversation() should only return messages from the specified team."""
        from delegate.bootstrap import bootstrap

        bootstrap(tmp_team, "alpha", manager="mgr-alpha", agents=["agent-alpha"])
        bootstrap(tmp_team, "beta", manager="mgr-beta", agents=["agent-beta"])

        # Create conversations in both teams
        alpha_id1 = send(tmp_team, "alpha", "mgr-alpha", "agent-alpha", "Alpha incoming")
        send(tmp_team, "alpha", "agent-alpha", "mgr-alpha", "Alpha outgoing")
        beta_id1 = send(tmp_team, "beta", "mgr-beta", "agent-beta", "Beta incoming")
        send(tmp_team, "beta", "agent-beta", "mgr-beta", "Beta outgoing")

        # Mark incoming messages as processed
        mark_processed(tmp_team, "alpha", alpha_id1)
        mark_processed(tmp_team, "beta", beta_id1)

        # Each team should only see its own conversation
        alpha_conv = recent_conversation(tmp_team, "alpha", "agent-alpha")
        beta_conv = recent_conversation(tmp_team, "beta", "agent-beta")

        assert len(alpha_conv) == 2
        assert set(m.body for m in alpha_conv) == {"Alpha incoming", "Alpha outgoing"}

        assert len(beta_conv) == 2
        assert set(m.body for m in beta_conv) == {"Beta incoming", "Beta outgoing"}

    def test_recent_conversation_with_peer_team_isolation(self, tmp_team):
        """recent_conversation() with peer should filter by team."""
        from delegate.bootstrap import bootstrap

        bootstrap(tmp_team, "alpha", manager="mgr-alpha", agents=["agent-alpha"])
        bootstrap(tmp_team, "beta", manager="mgr-beta", agents=["agent-beta"])

        # Create conversations with managers in both teams
        alpha_id = send(tmp_team, "alpha", "mgr-alpha", "agent-alpha", "Alpha msg")
        beta_id = send(tmp_team, "beta", "mgr-beta", "agent-beta", "Beta msg")

        mark_processed(tmp_team, "alpha", alpha_id)
        mark_processed(tmp_team, "beta", beta_id)

        # Filter by peer should still respect team boundaries
        alpha_conv = recent_conversation(tmp_team, "alpha", "agent-alpha", peer="mgr-alpha")
        beta_conv = recent_conversation(tmp_team, "beta", "agent-beta", peer="mgr-beta")

        assert len(alpha_conv) == 1
        assert alpha_conv[0].body == "Alpha msg"

        assert len(beta_conv) == 1
        assert beta_conv[0].body == "Beta msg"
