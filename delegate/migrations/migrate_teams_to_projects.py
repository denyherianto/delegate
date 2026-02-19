"""One-time filesystem migration: rename "teams" → "projects" storage layout.

This module contains the idempotent migration function that renames the
directory and config-file storage from the old "teams" naming to the new
"projects" naming.  It must be called at daemon startup, BEFORE
``ensure_schema()`` applies the V018 DB migration.

Migration steps (in order):
1. Sentinel check — if ``protected/.migrated_projects`` exists, skip.
2. Rename ``protected/teams/`` → ``protected/projects/``  (if old dir exists)
3. Rename ``teams/``           → ``projects/``            (if old dir exists)
4. Rename ``protected/team_map.json`` → ``protected/project_map.json``
   (if old file exists)
5. Write sentinel ``protected/.migrated_projects``

The DB schema rename (``teams`` → ``projects`` table, column renames) is
handled separately by the V018.sql migration file applied through the
normal ``ensure_schema()`` machinery.

The migration is re-runnable: if the sentinel is absent, each step checks
whether the source exists before acting, so a partial prior run is safely
continued.  Failures abort with a clear error message — the daemon should
not start in an inconsistent state.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SENTINEL_NAME = ".migrated_projects"


def _sentinel_path(hc_home: Path) -> Path:
    return hc_home / "protected" / _SENTINEL_NAME


def migrate_teams_to_projects(hc_home: Path) -> None:
    """Run the teams→projects filesystem migration idempotently.

    Args:
        hc_home: Delegate home directory (e.g. ``~/.delegate``).

    Raises:
        RuntimeError: If any migration step fails.  The daemon should
            treat this as a fatal error and refuse to start.
    """
    protected = hc_home / "protected"
    sentinel = _sentinel_path(hc_home)

    # Step 1: Sentinel check — already migrated, nothing to do.
    if sentinel.exists():
        logger.debug("teams→projects migration already applied (sentinel exists)")
        return

    logger.info("Running teams→projects filesystem migration …")

    # Step 2: Rename protected/teams/ → protected/projects/
    old_protected_teams = protected / "teams"
    new_protected_teams = protected / "projects"
    if old_protected_teams.is_dir():
        if new_protected_teams.exists():
            logger.warning(
                "Both protected/teams/ and protected/projects/ exist — "
                "skipping protected/teams/ rename (protected/projects/ wins)"
            )
        else:
            try:
                old_protected_teams.rename(new_protected_teams)
                logger.info("Renamed protected/teams/ → protected/projects/")
            except OSError as exc:
                raise RuntimeError(
                    f"Migration failed: could not rename {old_protected_teams} "
                    f"→ {new_protected_teams}: {exc}"
                ) from exc
    else:
        logger.debug("protected/teams/ not found — skipping rename (already done or fresh install)")

    # Step 3: Rename teams/ → projects/  (working data, may be large)
    old_teams = hc_home / "teams"
    new_teams = hc_home / "projects"
    if old_teams.is_dir():
        if new_teams.exists():
            logger.warning(
                "Both teams/ and projects/ exist — "
                "skipping teams/ rename (projects/ wins)"
            )
        else:
            try:
                old_teams.rename(new_teams)
                logger.info("Renamed teams/ → projects/")
            except OSError as exc:
                raise RuntimeError(
                    f"Migration failed: could not rename {old_teams} "
                    f"→ {new_teams}: {exc}"
                ) from exc
    else:
        logger.debug("teams/ not found — skipping rename (already done or fresh install)")

    # Step 4: Rename protected/team_map.json → protected/project_map.json
    old_map = protected / "team_map.json"
    new_map = protected / "project_map.json"
    if old_map.exists():
        if new_map.exists():
            logger.warning(
                "Both team_map.json and project_map.json exist — "
                "skipping team_map.json rename (project_map.json wins)"
            )
        else:
            try:
                old_map.rename(new_map)
                logger.info("Renamed protected/team_map.json → protected/project_map.json")
            except OSError as exc:
                raise RuntimeError(
                    f"Migration failed: could not rename {old_map} "
                    f"→ {new_map}: {exc}"
                ) from exc
    else:
        logger.debug("team_map.json not found — skipping rename (already done or fresh install)")

    # Step 5: Write sentinel to mark migration complete
    try:
        protected.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("migrated\n")
        logger.info("teams→projects migration complete — sentinel written")
    except OSError as exc:
        raise RuntimeError(
            f"Migration failed: could not write sentinel {sentinel}: {exc}"
        ) from exc
