"""Tests for UUID translation layer (db_ids.py)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from delegate.db import ensure_schema, get_connection
from delegate.db_ids import (
    lookup_member,
    lookup_team,
    register_member,
    register_team,
    resolve_member,
    resolve_member_flexible,
    resolve_team,
    soft_delete_team,
)


@pytest.fixture
def temp_hc_home():
    """Create a temporary hc_home directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hc_home = Path(tmpdir)
        # Ensure schema is set up
        ensure_schema(hc_home, "")
        yield hc_home


def test_register_and_resolve_team(temp_hc_home):
    """Test register_team + resolve_team roundtrip."""
    conn = get_connection(temp_hc_home, "")
    try:
        # Register a team
        team_uuid = register_team(conn, "test-team")
        assert len(team_uuid) == 32  # Full UUID
        conn.commit()

        # Resolve it back
        resolved_uuid = resolve_team(conn, "test-team")
        assert resolved_uuid == team_uuid
    finally:
        conn.close()


def test_register_and_resolve_agent(temp_hc_home):
    """Test register_member (agent) + resolve_member roundtrip."""
    conn = get_connection(temp_hc_home, "")
    try:
        # Register team first
        team_uuid = register_team(conn, "test-team")
        conn.commit()

        # Register agent
        agent_uuid = register_member(conn, "agent", team_uuid, "agent-1")
        assert len(agent_uuid) == 32
        conn.commit()

        # Resolve it back
        resolved_uuid = resolve_member(conn, "agent", team_uuid, "agent-1")
        assert resolved_uuid == agent_uuid
    finally:
        conn.close()


def test_register_and_resolve_human(temp_hc_home):
    """Test register_member (human) + resolve_member roundtrip."""
    conn = get_connection(temp_hc_home, "")
    try:
        # Register human (team_uuid=None)
        human_uuid = register_member(conn, "human", None, "alice")
        assert len(human_uuid) == 32
        conn.commit()

        # Resolve it back
        resolved_uuid = resolve_member(conn, "human", None, "alice")
        assert resolved_uuid == human_uuid
    finally:
        conn.close()


def test_resolve_member_flexible_agent_first(temp_hc_home):
    """Test resolve_member_flexible resolves agent first."""
    conn = get_connection(temp_hc_home, "")
    try:
        # Register team
        team_uuid = register_team(conn, "test-team")
        conn.commit()

        # Register agent
        agent_uuid = register_member(conn, "agent", team_uuid, "alice")
        conn.commit()

        # Register human with same name
        human_uuid = register_member(conn, "human", None, "alice")
        conn.commit()

        # Flexible resolve should return agent UUID (agent has priority)
        resolved_uuid = resolve_member_flexible(conn, team_uuid, "alice")
        assert resolved_uuid == agent_uuid
        assert resolved_uuid != human_uuid
    finally:
        conn.close()


def test_resolve_member_flexible_fallback_to_human(temp_hc_home):
    """Test resolve_member_flexible falls back to human."""
    conn = get_connection(temp_hc_home, "")
    try:
        # Register team
        team_uuid = register_team(conn, "test-team")
        conn.commit()

        # Register human only (no agent)
        human_uuid = register_member(conn, "human", None, "bob")
        conn.commit()

        # Flexible resolve should fall back to human
        resolved_uuid = resolve_member_flexible(conn, team_uuid, "bob")
        assert resolved_uuid == human_uuid
    finally:
        conn.close()


def test_soft_delete_team_marks_deleted(temp_hc_home):
    """Test soft_delete_team marks team and agents deleted."""
    conn = get_connection(temp_hc_home, "")
    try:
        # Register team and agents
        team_uuid = register_team(conn, "test-team")
        agent1_uuid = register_member(conn, "agent", team_uuid, "agent-1")
        agent2_uuid = register_member(conn, "agent", team_uuid, "agent-2")
        conn.commit()

        # Soft delete
        soft_delete_team(conn, team_uuid)
        conn.commit()

        # Resolve should fail (deleted=1)
        with pytest.raises(ValueError, match="No active team found"):
            resolve_team(conn, "test-team")

        with pytest.raises(ValueError, match="No active agent found"):
            resolve_member(conn, "agent", team_uuid, "agent-1")

        with pytest.raises(ValueError, match="No active agent found"):
            resolve_member(conn, "agent", team_uuid, "agent-2")
    finally:
        conn.close()


def test_soft_delete_then_recreate_new_uuid(temp_hc_home):
    """Test that re-registering after soft delete creates new UUID."""
    conn = get_connection(temp_hc_home, "")
    try:
        # Register team
        team_uuid_1 = register_team(conn, "test-team")
        conn.commit()

        # Soft delete
        soft_delete_team(conn, team_uuid_1)
        conn.commit()

        # Re-register same name
        team_uuid_2 = register_team(conn, "test-team")
        conn.commit()

        # Should get a new UUID
        assert team_uuid_2 != team_uuid_1
        assert len(team_uuid_2) == 32

        # Resolve should return the new UUID
        resolved_uuid = resolve_team(conn, "test-team")
        assert resolved_uuid == team_uuid_2
    finally:
        conn.close()


def test_lookup_team(temp_hc_home):
    """Test lookup_team UUID -> name."""
    conn = get_connection(temp_hc_home, "")
    try:
        team_uuid = register_team(conn, "my-team")
        conn.commit()

        # Lookup by UUID
        name = lookup_team(conn, team_uuid)
        assert name == "my-team"
    finally:
        conn.close()


def test_lookup_member(temp_hc_home):
    """Test lookup_member UUID -> (kind, team_uuid, name)."""
    conn = get_connection(temp_hc_home, "")
    try:
        # Register team and agent
        team_uuid = register_team(conn, "test-team")
        agent_uuid = register_member(conn, "agent", team_uuid, "agent-1")
        conn.commit()

        # Lookup agent
        kind, team_uuid_lookup, name = lookup_member(conn, agent_uuid)
        assert kind == "agent"
        assert team_uuid_lookup == team_uuid
        assert name == "agent-1"

        # Register and lookup human
        human_uuid = register_member(conn, "human", None, "alice")
        conn.commit()

        kind, team_uuid_lookup, name = lookup_member(conn, human_uuid)
        assert kind == "human"
        assert team_uuid_lookup is None
        assert name == "alice"
    finally:
        conn.close()


def test_backfill_from_filesystem(temp_hc_home):
    """Test backfill populates team_ids and member_ids from filesystem."""
    # Create team directories manually
    teams_dir = temp_hc_home / "teams"
    teams_dir.mkdir(parents=True, exist_ok=True)

    team_dir = teams_dir / "test-team"
    team_dir.mkdir()

    agents_dir = team_dir / "agents"
    agents_dir.mkdir()

    agent1_dir = agents_dir / "agent-1"
    agent1_dir.mkdir()

    agent2_dir = agents_dir / "agent-2"
    agent2_dir.mkdir()

    # Create members dir with human (in protected/)
    from delegate.paths import members_dir as _members_dir
    mdir = _members_dir(temp_hc_home)
    mdir.mkdir(parents=True, exist_ok=True)
    (mdir / "alice.yaml").write_text("name: alice\nkind: human\n")

    # Insert team into teams table
    conn = get_connection(temp_hc_home, "")
    try:
        team_uuid = "abc12300000000000000000000000000"  # Padded 6-char
        conn.execute(
            "INSERT INTO teams (name, team_id) VALUES (?, ?)",
            ("test-team", team_uuid)
        )
        conn.commit()
    finally:
        conn.close()

    # Re-initialize schema (triggers backfill)
    from delegate.db import _backfill_uuid_tables
    conn = get_connection(temp_hc_home, "")
    try:
        _backfill_uuid_tables(conn, temp_hc_home)
        conn.commit()

        # Verify team_ids populated
        team_uuid_resolved = resolve_team(conn, "test-team")
        assert team_uuid_resolved == team_uuid

        # Verify member_ids populated for agents
        agent1_uuid = resolve_member(conn, "agent", team_uuid, "agent-1")
        assert len(agent1_uuid) == 32

        agent2_uuid = resolve_member(conn, "agent", team_uuid, "agent-2")
        assert len(agent2_uuid) == 32

        # Verify member_ids populated for human
        human_uuid = resolve_member(conn, "human", None, "alice")
        assert len(human_uuid) == 32
    finally:
        conn.close()


def test_resolve_nonexistent_team(temp_hc_home):
    """Test resolve_team raises ValueError for nonexistent team."""
    conn = get_connection(temp_hc_home, "")
    try:
        with pytest.raises(ValueError, match="No active team found"):
            resolve_team(conn, "nonexistent")
    finally:
        conn.close()


def test_resolve_nonexistent_member(temp_hc_home):
    """Test resolve_member raises ValueError for nonexistent member."""
    conn = get_connection(temp_hc_home, "")
    try:
        team_uuid = register_team(conn, "test-team")
        conn.commit()

        with pytest.raises(ValueError, match="No active agent found"):
            resolve_member(conn, "agent", team_uuid, "nonexistent")
    finally:
        conn.close()


def test_lookup_nonexistent_team(temp_hc_home):
    """Test lookup_team raises ValueError for unknown UUID."""
    conn = get_connection(temp_hc_home, "")
    try:
        with pytest.raises(ValueError, match="Unknown team UUID"):
            lookup_team(conn, "00000000000000000000000000000000")
    finally:
        conn.close()


def test_lookup_nonexistent_member(temp_hc_home):
    """Test lookup_member raises ValueError for unknown UUID."""
    conn = get_connection(temp_hc_home, "")
    try:
        with pytest.raises(ValueError, match="Unknown member UUID"):
            lookup_member(conn, "00000000000000000000000000000000")
    finally:
        conn.close()


def test_register_team_idempotent(temp_hc_home):
    """Test register_team called twice with same name returns same UUID."""
    conn = get_connection(temp_hc_home, "")
    try:
        # First registration
        team_uuid_1 = register_team(conn, "myteam")
        assert len(team_uuid_1) == 32
        conn.commit()

        # Second registration with same name - should be idempotent
        team_uuid_2 = register_team(conn, "myteam")
        conn.commit()

        # Should return the same UUID, no error
        assert team_uuid_2 == team_uuid_1
    finally:
        conn.close()


def test_register_member_idempotent(temp_hc_home):
    """Test register_member called twice with same params returns same UUID."""
    conn = get_connection(temp_hc_home, "")
    try:
        # Register team first
        team_uuid = register_team(conn, "test-team")
        conn.commit()

        # First registration of agent
        agent_uuid_1 = register_member(conn, "agent", team_uuid, "agent-1")
        assert len(agent_uuid_1) == 32
        conn.commit()

        # Second registration with same params - should be idempotent
        agent_uuid_2 = register_member(conn, "agent", team_uuid, "agent-1")
        conn.commit()

        # Should return the same UUID, no error
        assert agent_uuid_2 == agent_uuid_1

        # Also test for human (team_uuid=None)
        human_uuid_1 = register_member(conn, "human", None, "alice")
        conn.commit()

        human_uuid_2 = register_member(conn, "human", None, "alice")
        conn.commit()

        assert human_uuid_2 == human_uuid_1
    finally:
        conn.close()
