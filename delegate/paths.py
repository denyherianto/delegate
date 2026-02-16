"""Centralized path computations for Delegate.

All state lives under a single home directory (``~/.delegate`` by default).
The ``DELEGATE_HOME`` environment variable overrides the default for testing.

Layout::

    ~/.delegate/
      protected/                  # Infrastructure (outside agent sandbox)
        daemon.pid
        delegate.log
        db.sqlite
        config.yaml
        network.yaml
        members/
        teams/<team>/
          repos.yaml
          roster.md
          team_id
      teams/                      # Working data (inside agent sandbox)
        <team>/
          override.md
          agents/<agent>/
          shared/
          worktrees/
"""

import os
from pathlib import Path

_DEFAULT_HOME = Path.home() / ".delegate"


def home(override: Path | None = None) -> Path:
    """Return the Delegate home directory.

    Resolution order:
    1. *override* argument (used in tests)
    2. ``DELEGATE_HOME`` environment variable
    3. ``~/.delegate``
    """
    if override is not None:
        return override
    env = os.environ.get("DELEGATE_HOME")
    if env:
        return Path(env)
    return _DEFAULT_HOME


# =========================================================================
# Protected directory — infrastructure, outside agent sandbox
# =========================================================================

def protected_dir(hc_home: Path) -> Path:
    """Root of protected infrastructure: ``<home>/protected/``."""
    return hc_home / "protected"


def protected_team_dir(hc_home: Path, team: str) -> Path:
    """Per-team metadata inside protected: ``protected/teams/<team>/``."""
    return protected_dir(hc_home) / "teams" / team


# --- Global infrastructure ---

def global_db_path(hc_home: Path) -> Path:
    """Global SQLite database: ``protected/db.sqlite``."""
    return protected_dir(hc_home) / "db.sqlite"


def daemon_pid_path(hc_home: Path) -> Path:
    """Daemon PID file: ``protected/daemon.pid``."""
    return protected_dir(hc_home) / "daemon.pid"


def config_path(hc_home: Path) -> Path:
    """Global config: ``protected/config.yaml``."""
    return protected_dir(hc_home) / "config.yaml"


def network_config_path(hc_home: Path) -> Path:
    """Network allowlist: ``protected/network.yaml``."""
    return protected_dir(hc_home) / "network.yaml"


# --- Members (org-wide, outside any team) ---

def members_dir(hc_home: Path) -> Path:
    """Directory containing human member YAML files: ``protected/members/``."""
    return protected_dir(hc_home) / "members"


def member_path(hc_home: Path, name: str) -> Path:
    """Path to a specific member's YAML file."""
    return members_dir(hc_home) / f"{name}.yaml"


# --- Per-team metadata (inside protected/) ---

def roster_path(hc_home: Path, team: str) -> Path:
    """Team roster: ``protected/teams/<team>/roster.md``."""
    return protected_team_dir(hc_home, team) / "roster.md"


def team_id_path(hc_home: Path, team: str) -> Path:
    """Path to the file storing the team's unique instance ID."""
    return protected_team_dir(hc_home, team) / "team_id"


def repos_config_path(hc_home: Path, team: str) -> Path:
    """Per-team repos config: ``protected/teams/<team>/repos.yaml``."""
    return protected_team_dir(hc_home, team) / "repos.yaml"


def get_team_id(hc_home: Path, team: str) -> str:
    """Read the 6-char hex team instance ID.

    Every team gets a random ID at bootstrap time.  This ID is embedded in
    branch names (``delegate/<team_id>/<team>/T<NNN>``) so that recreating
    a team with the same name doesn't collide with leftover branches.

    Falls back to the team name if the file doesn't exist (pre-migration
    teams).
    """
    p = team_id_path(hc_home, team)
    if p.exists():
        tid = p.read_text().strip()
        if tid:
            return tid
    return team


# =========================================================================
# Working data — teams directory (inside agent sandbox)
# =========================================================================

def teams_dir(hc_home: Path) -> Path:
    return hc_home / "teams"


def team_dir(hc_home: Path, team: str) -> Path:
    return teams_dir(hc_home) / team


# --- Per-team paths (working data) ---

def repos_dir(hc_home: Path, team: str) -> Path:
    """Per-team repo symlinks directory: ``teams/<team>/repos/``."""
    return team_dir(hc_home, team) / "repos"


def repo_path(hc_home: Path, team: str, name: str) -> Path:
    """Path to a specific repo symlink within a team."""
    return repos_dir(hc_home, team) / name


def agents_dir(hc_home: Path, team: str) -> Path:
    return team_dir(hc_home, team) / "agents"


def agent_dir(hc_home: Path, team: str, agent: str) -> Path:
    return agents_dir(hc_home, team) / agent


def agent_worktrees_dir(hc_home: Path, team: str, agent: str) -> Path:
    return agent_dir(hc_home, team, agent) / "worktrees"


def task_worktree_dir(hc_home: Path, team: str, repo_name: str, task_id: int) -> Path:
    """Per-task worktree directory: ``teams/{team}/worktrees/{repo}/T{id}/``."""
    from delegate.task import format_task_id
    return team_dir(hc_home, team) / "worktrees" / repo_name / format_task_id(task_id)


def shared_dir(hc_home: Path, team: str) -> Path:
    """Team-level shared knowledge base directory."""
    return team_dir(hc_home, team) / "shared"


def charter_dir(hc_home: Path, team: str) -> Path:
    """Team-level charter directory (for override.md)."""
    return team_dir(hc_home, team)


# --- Deprecated per-team db path (use global_db_path instead) ---

def db_path(hc_home: Path, team: str) -> Path:
    """Per-team SQLite database (deprecated — use global_db_path)."""
    return team_dir(hc_home, team) / "db.sqlite"


# --- Boss (deprecated — use members_dir) ---

def boss_person_dir(hc_home: Path) -> Path:
    """Boss's global directory (outside any team).

    .. deprecated:: Use ``members_dir`` instead.
    """
    return hc_home / "boss"


# --- Package-shipped charter (read-only, from installed package) ---

def base_charter_dir() -> Path:
    """Return the path to the base charter files shipped with the package."""
    return Path(__file__).parent / "charter"


# =========================================================================
# Bootstrap helpers — ensure directory structure exists
# =========================================================================

def ensure_protected(hc_home: Path) -> None:
    """Create the protected/ directory structure if it doesn't exist."""
    protected = protected_dir(hc_home)
    protected.mkdir(parents=True, exist_ok=True)
    (protected / "teams").mkdir(exist_ok=True)
    members_dir(hc_home).mkdir(exist_ok=True)


def ensure_protected_team(hc_home: Path, team: str) -> None:
    """Create the protected/teams/<team>/ directory."""
    protected_team_dir(hc_home, team).mkdir(parents=True, exist_ok=True)
