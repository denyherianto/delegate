"""Tests for activity.broadcast_turn_event."""

import pytest
from datetime import datetime, timezone
from delegate.activity import broadcast_turn_event, subscribe, unsubscribe


class TestBroadcastTurnEvent:
    """Test the broadcast_turn_event function for turn lifecycle events."""

    def test_turn_started_payload_structure(self):
        """Turn started event has correct payload structure."""
        q = subscribe()
        try:
            broadcast_turn_event('turn_started', 'alex', task_id=42, sender='nikhil')

            # Non-blocking get
            payload = q.get_nowait()

            assert payload['type'] == 'turn_started'
            assert payload['agent'] == 'alex'
            assert payload['task_id'] == 42
            assert payload['sender'] == 'nikhil'
            assert 'timestamp' in payload
            # Verify timestamp is valid ISO format
            datetime.fromisoformat(payload['timestamp'])
        finally:
            unsubscribe(q)

    def test_turn_ended_payload_structure(self):
        """Turn ended event has correct payload structure."""
        q = subscribe()
        try:
            broadcast_turn_event('turn_ended', 'alex', task_id=42, sender='nikhil')

            payload = q.get_nowait()

            assert payload['type'] == 'turn_ended'
            assert payload['agent'] == 'alex'
            assert payload['task_id'] == 42
            assert payload['sender'] == 'nikhil'
            assert 'timestamp' in payload
            datetime.fromisoformat(payload['timestamp'])
        finally:
            unsubscribe(q)

    def test_turn_event_with_null_task_id(self):
        """Turn event with task_id=None has correct structure."""
        q = subscribe()
        try:
            broadcast_turn_event('turn_started', 'alex', task_id=None, sender='boss')

            payload = q.get_nowait()

            assert payload['type'] == 'turn_started'
            assert payload['agent'] == 'alex'
            assert payload['task_id'] is None
            assert payload['sender'] == 'boss'
        finally:
            unsubscribe(q)

    def test_turn_event_with_empty_sender(self):
        """Turn event with empty sender string."""
        q = subscribe()
        try:
            broadcast_turn_event('turn_started', 'alex', task_id=1, sender='')

            payload = q.get_nowait()

            assert payload['sender'] == ''
        finally:
            unsubscribe(q)

    def test_multiple_subscribers_receive_event(self):
        """Multiple subscribers all receive the same event."""
        q1 = subscribe()
        q2 = subscribe()
        try:
            broadcast_turn_event('turn_started', 'alex', task_id=1, sender='boss')

            payload1 = q1.get_nowait()
            payload2 = q2.get_nowait()

            assert payload1 == payload2
        finally:
            unsubscribe(q1)
            unsubscribe(q2)
