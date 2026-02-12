"""Tests for runtime._select_batch message batching logic."""

import pytest
from delegate.mailbox import Message
from delegate.runtime import _select_batch


class TestSelectBatch:
    """Test the _select_batch function for message grouping."""

    def test_groups_by_task_id_when_present(self):
        """Messages with the same task_id are grouped together."""
        msgs = [
            Message(sender="alice", recipient="bob", time="2026-02-11T10:00:00Z", body="msg1", task_id=1),
            Message(sender="alice", recipient="bob", time="2026-02-11T10:01:00Z", body="msg2", task_id=1),
            Message(sender="charlie", recipient="bob", time="2026-02-11T10:02:00Z", body="msg3", task_id=2),
        ]
        batch = _select_batch(msgs)
        assert len(batch) == 2
        assert batch[0].body == "msg1"
        assert batch[1].body == "msg2"

    def test_groups_by_sender_when_task_id_is_none(self):
        """When task_id is None, messages are grouped by sender."""
        msgs = [
            Message(sender="alice", recipient="bob", time="2026-02-11T10:00:00Z", body="msg1", task_id=None),
            Message(sender="alice", recipient="bob", time="2026-02-11T10:01:00Z", body="msg2", task_id=None),
            Message(sender="charlie", recipient="bob", time="2026-02-11T10:02:00Z", body="msg3", task_id=None),
        ]
        batch = _select_batch(msgs)
        assert len(batch) == 2
        assert batch[0].body == "msg1"
        assert batch[1].body == "msg2"
        assert all(m.sender == "alice" for m in batch)

    def test_respects_max_size(self):
        """Batch size is limited by max_size parameter."""
        msgs = [
            Message(sender="alice", recipient="bob", time=f"2026-02-11T10:0{i}:00Z", body=f"msg{i}", task_id=1)
            for i in range(10)
        ]
        batch = _select_batch(msgs, max_size=3)
        assert len(batch) == 3

    def test_empty_inbox_returns_empty_batch(self):
        """Empty inbox returns empty batch."""
        batch = _select_batch([])
        assert batch == []

    def test_single_message_returns_single_item_batch(self):
        """Single message returns a batch with one item."""
        msgs = [
            Message(sender="alice", recipient="bob", time="2026-02-11T10:00:00Z", body="msg1", task_id=1),
        ]
        batch = _select_batch(msgs)
        assert len(batch) == 1
        assert batch[0].body == "msg1"

    def test_mixed_task_ids_and_none(self):
        """Task ID None and Task ID 1 should not be grouped together."""
        msgs = [
            Message(sender="alice", recipient="bob", time="2026-02-11T10:00:00Z", body="msg1", task_id=None),
            Message(sender="alice", recipient="bob", time="2026-02-11T10:01:00Z", body="msg2", task_id=1),
        ]
        batch = _select_batch(msgs)
        assert len(batch) == 1
        assert batch[0].task_id is None
