"""Tests for boss/bootstrap.py."""

import sqlite3

import pytest
import yaml

from boss.bootstrap import bootstrap, AGENT_SUBDIRS, get_member_by_role
from boss.config import set_boss, get_boss
from boss.paths import (
    team_dir, agents_dir, agent_dir, tasks_dir, db_path,
    roster_path, boss_person_dir, base_charter_dir,
)

TEAM = "testteam"


@pytest.fixture
def hc(tmp_path):
    """Return an hc_home with the boss name configured."""
    hc_home = tmp_path / "hc"
    hc_home.mkdir()
    set_boss(hc_home, "nikhil")
    return hc_home


def test_creates_directory_structure(tmp_team):
    """Bootstrap creates all expected directories for every agent."""
    hc_home = tmp_team
    td = team_dir(hc_home, TEAM)
    assert td.is_dir()
    assert tasks_dir(hc_home).is_dir()
    assert agents_dir(hc_home, TEAM).is_dir()

    for name in ["manager", "alice", "bob"]:
        ad = agent_dir(hc_home, TEAM, name)
        assert ad.is_dir(), f"Missing agent dir: {name}"
        for subdir in AGENT_SUBDIRS:
            assert (ad / subdir).is_dir(), f"Missing {name}/{subdir}"


def test_creates_starter_files(tmp_team):
    """Bootstrap creates all expected files with content."""
    hc_home = tmp_team
    assert roster_path(hc_home, TEAM).is_file()
    assert db_path(hc_home).is_file()

    for name in ["manager", "alice", "bob"]:
        ad = agent_dir(hc_home, TEAM, name)
        assert (ad / "bio.md").is_file()
        assert (ad / "context.md").is_file()
        assert (ad / "state.yaml").is_file()


def test_state_yaml_has_role(tmp_team):
    """Each agent's state.yaml includes the correct role."""
    hc_home = tmp_team
    state = yaml.safe_load((agent_dir(hc_home, TEAM, "manager") / "state.yaml").read_text())
    assert state["role"] == "manager"
    assert state["pid"] is None

    state = yaml.safe_load((agent_dir(hc_home, TEAM, "alice") / "state.yaml").read_text())
    assert state["role"] == "worker"


def test_boss_mailbox_created(tmp_team):
    """The boss's global mailbox directory is created outside any team."""
    hc_home = tmp_team
    bd = boss_person_dir(hc_home)
    assert bd.is_dir()
    for box in ["inbox", "outbox"]:
        for sub in ["new", "cur", "tmp"]:
            assert (bd / box / sub).is_dir()


def test_roster_contains_all_members(tmp_team):
    """Roster file lists every team member."""
    content = roster_path(tmp_team, TEAM).read_text()
    for name in ["manager", "alice", "bob", "nikhil"]:
        assert name in content


def test_roster_shows_roles(tmp_team):
    """Roster shows role annotations for manager and boss."""
    content = roster_path(tmp_team, TEAM).read_text()
    assert "(manager)" in content
    assert "(boss)" in content


def test_charter_shipped_with_package():
    """Base charter files are shipped with the package."""
    cd = base_charter_dir()
    assert cd.is_dir()
    expected = {"constitution.md", "communication.md", "task-management.md", "code-review.md", "manager.md"}
    actual = {f.name for f in cd.glob("*.md")}
    assert actual == expected
    for f in cd.glob("*.md"):
        assert len(f.read_text()) > 0


def test_maildir_subdirs_exist(tmp_team):
    """Each agent has Maildir-style new/cur/tmp under inbox and outbox."""
    hc_home = tmp_team
    for name in ["manager", "alice", "bob"]:
        for box in ["inbox", "outbox"]:
            for sub in ["new", "cur", "tmp"]:
                path = agent_dir(hc_home, TEAM, name) / box / sub
                assert path.is_dir(), f"Missing {name}/{box}/{sub}"


def test_workspace_exists_per_agent(tmp_team):
    """Each team agent has a workspace directory."""
    hc_home = tmp_team
    for name in ["manager", "alice", "bob"]:
        assert (agent_dir(hc_home, TEAM, name) / "workspace").is_dir()


def test_db_schema_created(tmp_team):
    """SQLite database has the messages and sessions tables."""
    conn = sqlite3.connect(str(db_path(tmp_team)))

    cursor = conn.execute("PRAGMA table_info(messages)")
    msg_columns = {row[1] for row in cursor.fetchall()}
    assert msg_columns == {"id", "timestamp", "sender", "recipient", "content", "type"}

    cursor = conn.execute("PRAGMA table_info(sessions)")
    sess_columns = {row[1] for row in cursor.fetchall()}
    assert sess_columns == {
        "id", "agent", "task_id", "started_at", "ended_at",
        "duration_seconds", "tokens_in", "tokens_out", "cost_usd",
    }

    conn.close()


def test_idempotent_rerun(hc):
    """Running bootstrap twice doesn't corrupt existing files."""
    bootstrap(hc, TEAM, manager="mgr", agents=["a", "b"])
    bootstrap(hc, TEAM, manager="mgr", agents=["a", "b"])

    for name in ["mgr", "a", "b"]:
        assert (agent_dir(hc, TEAM, name) / "state.yaml").is_file()


def test_bio_default_content(tmp_team):
    """Each agent's bio.md has their name as a simple placeholder."""
    hc_home = tmp_team
    for name in ["manager", "alice", "bob"]:
        content = (agent_dir(hc_home, TEAM, name) / "bio.md").read_text()
        assert name in content
        assert content.strip() == f"# {name}"


def test_get_member_by_role(tmp_team):
    """get_member_by_role finds the correct member for each role."""
    assert get_member_by_role(tmp_team, TEAM, "manager") == "manager"
    assert get_member_by_role(tmp_team, TEAM, "nonexistent") is None


def test_get_member_by_role_custom_names(hc):
    """get_member_by_role works with custom names."""
    bootstrap(hc, TEAM, manager="edison", agents=["alice"])
    assert get_member_by_role(hc, TEAM, "manager") == "edison"


def test_duplicate_names_raises(hc):
    """Bootstrap rejects duplicate member names."""
    with pytest.raises(ValueError, match="Duplicate"):
        bootstrap(hc, TEAM, manager="alice", agents=["alice"])


def test_interactive_bios(tmp_path, monkeypatch):
    """Interactive mode prompts for bios and writes them."""
    hc_home = tmp_path / "hc"
    hc_home.mkdir()
    set_boss(hc_home, "nikhil")

    # Order: additional charter prompt first, then bios for each member
    inputs = iter([
        "",                   # no additional charter
        "Great at planning",  # manager bio line 1
        "",                   # end manager bio
        "Python expert",      # alice bio line 1
        "",                   # end alice bio
    ])
    monkeypatch.setattr("builtins.input", lambda: next(inputs))

    bootstrap(hc_home, TEAM, manager="mgr", agents=["alice"], interactive=True)

    assert "Great at planning" in (agent_dir(hc_home, TEAM, "mgr") / "bio.md").read_text()
    assert "Python expert" in (agent_dir(hc_home, TEAM, "alice") / "bio.md").read_text()


def test_interactive_extra_charter(tmp_path, monkeypatch):
    """Interactive mode can add additional charter material."""
    hc_home = tmp_path / "hc"
    hc_home.mkdir()
    set_boss(hc_home, "nikhil")

    # Order: additional charter prompt first, then bios
    inputs = iter([
        "We use Rust for infrastructure",  # extra charter line 1
        "",                                 # end extra charter
        "",                                 # empty bio for manager
    ])
    monkeypatch.setattr("builtins.input", lambda: next(inputs))

    bootstrap(hc_home, TEAM, manager="mgr", agents=[], interactive=True)

    override = team_dir(hc_home, TEAM) / "override.md"
    assert override.exists()
    assert "Rust for infrastructure" in override.read_text()
