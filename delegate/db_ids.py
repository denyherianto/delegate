"""UUID translation layer for team and member identities.

This module provides functions to resolve names to UUIDs and vice versa,
manage the team_ids and member_ids translation tables, and handle entity
registration and soft deletion.

All DB-facing code should use UUIDs for queries (via resolve_* functions)
but continue to work with names in their public APIs. The translation is
transparent to callers.
"""

import functools
import sqlite3
import uuid as uuid_module
from typing import Literal


# In-process LRU cache for resolve operations (invalidated on register/delete)
# Cache key: (table, *args) -> result
@functools.lru_cache(maxsize=1024)
def _resolve_team_cached(name: str) -> str:
    """Internal cached resolver. Do not call directly."""
    # This is just a placeholder -- actual resolution happens in resolve_team
    raise NotImplementedError("Use resolve_team instead")


@functools.lru_cache(maxsize=2048)
def _resolve_member_cached(kind: str, team_uuid: str | None, name: str) -> str:
    """Internal cached resolver. Do not call directly."""
    raise NotImplementedError("Use resolve_member instead")


def _invalidate_caches():
    """Clear all LRU caches after mutations."""
    _resolve_team_cached.cache_clear()
    _resolve_member_cached.cache_clear()


# ---------------------------------------------------------------------------
# Resolve: name -> UUID
# ---------------------------------------------------------------------------

def resolve_team(conn: sqlite3.Connection, name: str) -> str:
    """Name -> UUID for active (non-deleted) team.

    Args:
        conn: Database connection
        name: Team name

    Returns:
        32-char hex UUID string

    Raises:
        ValueError: If no active team found with that name
    """
    row = conn.execute(
        "SELECT uuid FROM team_ids WHERE name = ? AND deleted = 0", (name,)
    ).fetchone()
    if not row:
        raise ValueError(f"No active team found: {name}")
    return row[0]


def resolve_member(
    conn: sqlite3.Connection,
    kind: Literal["agent", "human"],
    team_uuid: str | None,
    name: str
) -> str:
    """Name -> UUID for active agent or human.

    Args:
        conn: Database connection
        kind: 'agent' or 'human'
        team_uuid: Parent team UUID for agents; None for humans
        name: Member name

    Returns:
        32-char hex UUID string

    Raises:
        ValueError: If no active member found
    """
    if team_uuid is None:
        row = conn.execute(
            "SELECT uuid FROM member_ids WHERE kind = ? AND team_uuid IS NULL AND name = ? AND deleted = 0",
            (kind, name)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT uuid FROM member_ids WHERE kind = ? AND team_uuid = ? AND name = ? AND deleted = 0",
            (kind, team_uuid, name)
        ).fetchone()
    if not row:
        raise ValueError(f"No active {kind} found: {name} (team_uuid={team_uuid})")
    return row[0]


def resolve_member_flexible(conn: sqlite3.Connection, team_uuid: str, name: str) -> str:
    """Resolve a name that could be either an agent or human.

    First tries agent in the given team, then falls back to human (global).
    This is the common case for sender/recipient/assignee fields where
    the caller doesn't know if the name is an agent or human.

    Args:
        conn: Database connection
        team_uuid: Team UUID to check for agents
        name: Member name

    Returns:
        32-char hex UUID string

    Raises:
        ValueError: If no active agent or human found
    """
    # Try agent first
    row = conn.execute(
        "SELECT uuid FROM member_ids WHERE kind = 'agent' AND team_uuid = ? AND name = ? AND deleted = 0",
        (team_uuid, name)
    ).fetchone()
    if row:
        return row[0]

    # Fall back to human
    row = conn.execute(
        "SELECT uuid FROM member_ids WHERE kind = 'human' AND team_uuid IS NULL AND name = ? AND deleted = 0",
        (name,)
    ).fetchone()
    if not row:
        raise ValueError(f"No active agent or human found: {name} (team_uuid={team_uuid})")
    return row[0]


# ---------------------------------------------------------------------------
# Lookup: UUID -> name
# ---------------------------------------------------------------------------

def lookup_team(conn: sqlite3.Connection, team_uuid: str) -> str:
    """UUID -> team name.

    Args:
        conn: Database connection
        team_uuid: Team UUID

    Returns:
        Team name

    Raises:
        ValueError: If unknown team UUID
    """
    row = conn.execute("SELECT name FROM team_ids WHERE uuid = ?", (team_uuid,)).fetchone()
    if not row:
        raise ValueError(f"Unknown team UUID: {team_uuid}")
    return row[0]


def lookup_member(conn: sqlite3.Connection, member_uuid: str) -> tuple[str, str | None, str]:
    """UUID -> (kind, team_uuid_or_none, name).

    Args:
        conn: Database connection
        member_uuid: Member UUID

    Returns:
        Tuple of (kind, team_uuid, name). team_uuid is None for humans.

    Raises:
        ValueError: If unknown member UUID
    """
    row = conn.execute(
        "SELECT kind, team_uuid, name FROM member_ids WHERE uuid = ?", (member_uuid,)
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown member UUID: {member_uuid}")
    return (row[0], row[1], row[2])


# ---------------------------------------------------------------------------
# Register: create new entities
# ---------------------------------------------------------------------------

def register_team(conn: sqlite3.Connection, name: str, *, team_uuid: str | None = None) -> str:
    """Generate uuid4, insert into team_ids, return full 32-char hex UUID.

    Args:
        conn: Database connection
        name: Team name
        team_uuid: Optional UUID to use (for bootstrapping). If None, generates uuid4.

    Returns:
        32-char hex UUID string
    """
    new_uuid = team_uuid or uuid_module.uuid4().hex
    conn.execute(
        "INSERT INTO team_ids (uuid, name) VALUES (?, ?)",
        (new_uuid, name)
    )
    _invalidate_caches()
    return new_uuid


def register_member(
    conn: sqlite3.Connection,
    kind: Literal["agent", "human"],
    team_uuid: str | None,
    name: str
) -> str:
    """Generate uuid4, insert into member_ids, return UUID.

    Args:
        conn: Database connection
        kind: 'agent' or 'human'
        team_uuid: Parent team UUID for agents; None for humans
        name: Member name

    Returns:
        32-char hex UUID string
    """
    new_uuid = uuid_module.uuid4().hex
    conn.execute(
        "INSERT INTO member_ids (uuid, kind, team_uuid, name) VALUES (?, ?, ?, ?)",
        (new_uuid, kind, team_uuid, name)
    )
    _invalidate_caches()
    return new_uuid


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

def soft_delete_team(conn: sqlite3.Connection, team_uuid: str):
    """Mark team and all its agents as deleted=1.

    Args:
        conn: Database connection
        team_uuid: Team UUID to delete
    """
    conn.execute("UPDATE team_ids SET deleted = 1 WHERE uuid = ?", (team_uuid,))
    conn.execute("UPDATE member_ids SET deleted = 1 WHERE team_uuid = ?", (team_uuid,))
    _invalidate_caches()
