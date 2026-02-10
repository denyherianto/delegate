"""Migrate existing myteam/.standup state to the new ~/.delegate structure.

Migration steps:
1. Create ~/.delegate/ structure
2. Copy tasks/ to ~/.delegate/tasks/
3. Copy db.sqlite to ~/.delegate/db.sqlite
4. Copy charter/additional.md to ~/.delegate/teams/<name>/override.md
5. Copy roster.md to ~/.delegate/teams/<name>/roster.md
6. Move team/ to ~/.delegate/teams/<name>/agents/ (excluding boss)
7. Extract boss name from state.yaml and write to config.yaml
8. Update state.yaml: remove stale boss entries; set qa role

Usage:
    boss migrate <old_root> <team_name> [--home ~/.delegate]
"""

import argparse
import logging
import shutil
from pathlib import Path

import yaml

from delegate.paths import (
    home as _default_home,
    tasks_dir,
    db_path,
    team_dir,
    agents_dir,
    roster_path,
    boss_person_dir,
)
from delegate.bootstrap import MAILDIR_SUBDIRS
from delegate.config import set_boss

logger = logging.getLogger(__name__)


def migrate(
    old_root: Path,
    team_name: str,
    hc_home: Path | None = None,
) -> dict:
    """Migrate old .standup state to the new ~/.delegate structure.

    Args:
        old_root: Path to the old project root containing .standup/
        team_name: Name for the team in the new structure
        hc_home: Delegate home (default: ~/.delegate)

    Returns:
        Migration report dict with counts and details.
    """
    hc_home = hc_home or _default_home()
    old_standup = old_root / ".standup"

    if not old_standup.is_dir():
        raise FileNotFoundError(f"No .standup directory found at {old_standup}")

    report: dict = {
        "old_root": str(old_root),
        "hc_home": str(hc_home),
        "team_name": team_name,
        "tasks_copied": 0,
        "db_copied": False,
        "agents_migrated": [],
        "boss_name": None,
        "charter_override": False,
        "roster_copied": False,
    }

    # Ensure base bossies
    hc_home.mkdir(parents=True, exist_ok=True)

    # --- 1. Copy tasks/ ---
    old_tasks = old_standup / "tasks"
    new_tasks = tasks_dir(hc_home)
    if old_tasks.is_dir():
        new_tasks.mkdir(parents=True, exist_ok=True)
        count = 0
        for f in old_tasks.glob("T*.yaml"):
            dest = new_tasks / f.name
            if not dest.exists():
                shutil.copy2(f, dest)
                count += 1
            else:
                logger.info("Task %s already exists, skipping", f.name)
        report["tasks_copied"] = count
        logger.info("Copied %d task files", count)

    # --- 2. Copy db.sqlite ---
    old_db = old_standup / "db.sqlite"
    new_db = db_path(hc_home)
    if old_db.is_file() and not new_db.exists():
        new_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_db, new_db)
        report["db_copied"] = True
        logger.info("Copied db.sqlite")

    # --- 3. Team directory ---
    td = team_dir(hc_home, team_name)
    td.mkdir(parents=True, exist_ok=True)

    # --- 4. Copy charter/additional.md -> override.md ---
    old_charter = old_standup / "charter"
    if old_charter.is_dir():
        additional = old_charter / "additional.md"
        if additional.is_file() and additional.read_text().strip():
            override_path = td / "override.md"
            if not override_path.exists():
                content = additional.read_text()
                override_path.write_text(content)
                report["charter_override"] = True
                logger.info("Copied additional.md -> override.md")

    # --- 5. Copy roster.md ---
    old_roster = old_standup / "roster.md"
    new_roster = roster_path(hc_home, team_name)
    if old_roster.is_file() and not new_roster.exists():
        shutil.copy2(old_roster, new_roster)
        report["roster_copied"] = True
        logger.info("Copied roster.md")

    # --- 6. Move team/ -> agents/ (excluding boss) ---
    old_team = old_standup / "team"
    new_agents = agents_dir(hc_home, team_name)

    boss_name = None

    if old_team.is_dir():
        new_agents.mkdir(parents=True, exist_ok=True)

        for agent_dir in sorted(old_team.iterdir()):
            if not agent_dir.is_dir():
                continue

            # Check if this is the boss
            state_file = agent_dir / "state.yaml"
            is_boss = False
            if state_file.is_file():
                state = yaml.safe_load(state_file.read_text()) or {}
                if state.get("role") == "boss":
                    is_boss = True
                    boss_name = agent_dir.name
                    logger.info("Found boss: %s (not migrating as agent)", boss_name)
                    continue

            # Copy agent directory
            dest = new_agents / agent_dir.name
            if not dest.exists():
                shutil.copytree(agent_dir, dest)
                report["agents_migrated"].append(agent_dir.name)
                logger.info("Migrated agent: %s", agent_dir.name)
            else:
                logger.info("Agent %s already exists, skipping", agent_dir.name)

    # --- 7. Set boss name in config & create boss mailbox ---
    if boss_name:
        set_boss(hc_home, boss_name)
        report["boss_name"] = boss_name
        logger.info("Set boss to: %s", boss_name)

        # Create boss's global mailbox at ~/.delegate/boss/
        dd = boss_person_dir(hc_home)
        dd.mkdir(parents=True, exist_ok=True)
        for subdir in MAILDIR_SUBDIRS:
            (dd / subdir).mkdir(parents=True, exist_ok=True)
        logger.info("Created boss mailbox at %s", dd)

    # --- 8. Update state.yaml files ---
    if new_agents.is_dir():
        for agent_dir_path in sorted(new_agents.iterdir()):
            if not agent_dir_path.is_dir():
                continue
            state_file = agent_dir_path / "state.yaml"
            if not state_file.is_file():
                continue

            state = yaml.safe_load(state_file.read_text()) or {}
            changed = False

            # Remove stale boss role
            if state.get("role") == "boss":
                state["role"] = "worker"
                changed = True
                logger.info("Updated %s: role boss -> worker", agent_dir_path.name)

            # Agent named "qa" gets qa role
            if agent_dir_path.name.lower() == "qa" and state.get("role") != "qa":
                state["role"] = "qa"
                changed = True
                logger.info("Updated %s: role -> qa", agent_dir_path.name)

            # Clear stale PID
            if state.get("pid") is not None:
                state["pid"] = None
                changed = True

            if changed:
                state_file.write_text(yaml.dump(state, default_flow_style=False))

    return report


def print_migration_report(report: dict) -> None:
    """Print a formatted migration report."""
    print("\nMigration Report")
    print("=" * 50)
    print(f"  Old root:  {report['old_root']}")
    print(f"  New home:  {report['hc_home']}")
    print(f"  Team:      {report['team_name']}")
    print()
    print(f"  Tasks copied:       {report['tasks_copied']}")
    print(f"  DB copied:          {report['db_copied']}")
    print(f"  Agents migrated:    {', '.join(report['agents_migrated']) or 'none'}")
    print(f"  Boss name:      {report['boss_name'] or 'not found'}")
    print(f"  Charter override:   {report['charter_override']}")
    print(f"  Roster copied:      {report['roster_copied']}")
    print()
    print("Migration complete. ✓")


def main():
    parser = argparse.ArgumentParser(description="Migrate .standup state to ~/.delegate")
    parser.add_argument("old_root", type=Path, help="Path to old project root (with .standup/)")
    parser.add_argument("team_name", help="Name for the team in the new structure")
    parser.add_argument(
        "--home", type=Path, default=None,
        help="Delegate home directory (default: ~/.delegate)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    report = migrate(args.old_root, args.team_name, hc_home=args.home)
    print_migration_report(report)


if __name__ == "__main__":
    main()
