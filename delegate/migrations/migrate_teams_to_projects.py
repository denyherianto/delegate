"""One-time filesystem migration: rename "teams" → "projects" storage layout.

Called from ``daemon.start()`` BEFORE ``ensure_protected()`` so the new
directories don't exist yet and ``rename()`` works atomically.

Migration steps (in order):
1. Sentinel check — if ``protected/.migrated_projects`` exists, skip.
2. Rename ``protected/teams/`` → ``protected/projects/``
3. Rename ``teams/`` → ``projects/``
4. Rename ``protected/team_map.json`` → ``protected/project_map.json``
5. Write sentinel ``protected/.migrated_projects``

If neither old directory exists (fresh install), no sentinel is written
and the migration becomes a no-op.  The sentinel + migration code can
be removed entirely once all users have upgraded past 0.2.x.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SENTINEL_NAME = ".migrated_projects"


def _sentinel_path(hc_home: Path) -> Path:
    return hc_home / "protected" / _SENTINEL_NAME


def _rename_dir(src: Path, dst: Path, label: str) -> None:
    """Rename *src* → *dst*.  No-op if *src* doesn't exist."""
    if not src.is_dir():
        logger.debug("%s not found — nothing to migrate", label)
        return
    if dst.exists():
        # Target already exists (shouldn't happen when called before
        # ensure_protected, but be defensive).
        logger.debug("%s target already exists — skipping", label)
        return
    try:
        src.rename(dst)
        logger.info("Renamed %s → %s", src, dst)
    except OSError as exc:
        raise RuntimeError(
            f"Migration failed: could not rename {src} → {dst}: {exc}"
        ) from exc


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

    # Already migrated — nothing to do.
    if sentinel.exists():
        logger.debug("teams→projects migration already applied (sentinel exists)")
        return

    old_protected_teams = protected / "teams"
    old_teams = hc_home / "teams"
    old_map = protected / "team_map.json"

    # Fresh install — no old dirs/files to migrate.  Skip sentinel too.
    if not old_protected_teams.exists() and not old_teams.exists() and not old_map.exists():
        logger.debug("No teams/ directories found — fresh install, skipping migration")
        return

    logger.info("Running teams→projects filesystem migration …")

    _rename_dir(old_protected_teams, protected / "projects", "protected/teams")
    _rename_dir(old_teams, hc_home / "projects", "teams")

    # Rename team_map.json → project_map.json
    new_map = protected / "project_map.json"
    if old_map.exists() and not new_map.exists():
        try:
            old_map.rename(new_map)
            logger.info("Renamed %s → %s", old_map, new_map)
        except OSError as exc:
            raise RuntimeError(
                f"Migration failed: could not rename {old_map} → {new_map}: {exc}"
            ) from exc

    # Write sentinel so we don't re-run.
    try:
        protected.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("migrated\n")
        logger.info("teams→projects migration complete — sentinel written")
    except OSError as exc:
        raise RuntimeError(
            f"Migration failed: could not write sentinel {sentinel}: {exc}"
        ) from exc
