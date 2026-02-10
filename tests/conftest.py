"""Shared test fixtures for delegate-ai tests."""

import os
import sys
from pathlib import Path

import pytest

# Ensure the worktree's delegate/ directory is on the package path so that
# new modules (e.g. delegate.notify) are importable even before the branch
# is merged to main and installed.
_worktree_hc = str(Path(__file__).resolve().parent.parent / "delegate")
import delegate  # noqa: E402
if _worktree_hc not in delegate.__path__:
    delegate.__path__.insert(0, _worktree_hc)

from delegate.bootstrap import bootstrap
from delegate.config import set_boss


SAMPLE_MANAGER = "manager"
SAMPLE_BOSS = "nikhil"
SAMPLE_WORKERS = ["alice", "bob"]
SAMPLE_TEAM_NAME = "testteam"


@pytest.fixture
def sample_agents():
    """Return a standard list of all agent (non-boss) names for testing."""
    return [SAMPLE_MANAGER] + list(SAMPLE_WORKERS)


@pytest.fixture
def all_members():
    """Return all member names including boss."""
    return [SAMPLE_MANAGER, SAMPLE_BOSS] + list(SAMPLE_WORKERS)


@pytest.fixture
def tmp_team(tmp_path):
    """Create a fully bootstrapped team directory tree in a temp folder.

    Returns the hc_home path. Every test gets an isolated, disposable team.
    Uses the real bootstrap() function.
    """
    hc_home = tmp_path / "hc"
    hc_home.mkdir()
    # Set the boss name in config before bootstrap
    set_boss(hc_home, SAMPLE_BOSS)
    bootstrap(hc_home, SAMPLE_TEAM_NAME, manager=SAMPLE_MANAGER, agents=SAMPLE_WORKERS)
    # Set DELEGATE_HOME so modules can find it
    old_env = os.environ.get("DELEGATE_HOME")
    os.environ["DELEGATE_HOME"] = str(hc_home)
    yield hc_home
    if old_env is None:
        os.environ.pop("DELEGATE_HOME", None)
    else:
        os.environ["DELEGATE_HOME"] = old_env
