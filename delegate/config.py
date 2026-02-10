"""Org-wide configuration stored in ``~/.delegate/config.yaml``.

Manages:
- boss name (single human boss across all teams)
- source_repo path (for self-update)
- registered repos
"""

from pathlib import Path

import yaml

from delegate.paths import config_path


def _read(hc_home: Path) -> dict:
    """Read config.yaml, returning empty dict if missing."""
    cp = config_path(hc_home)
    if cp.exists():
        return yaml.safe_load(cp.read_text()) or {}
    return {}


def _write(hc_home: Path, data: dict) -> None:
    """Write config.yaml (creates parent dirs if needed)."""
    cp = config_path(hc_home)
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


# --- Boss ---

def get_boss(hc_home: Path) -> str | None:
    """Return the org-wide boss name, or None if not set."""
    return _read(hc_home).get("boss")


def set_boss(hc_home: Path, name: str) -> None:
    """Set the org-wide boss name."""
    data = _read(hc_home)
    data["boss"] = name
    _write(hc_home, data)


# --- Source repo (for self-update) ---

def get_source_repo(hc_home: Path) -> Path | None:
    """Return path to delegate's own source repo, or None."""
    val = _read(hc_home).get("source_repo")
    return Path(val) if val else None


def set_source_repo(hc_home: Path, path: Path) -> None:
    """Set the boss source repo path."""
    data = _read(hc_home)
    data["source_repo"] = str(path)
    _write(hc_home, data)


# --- Repos ---

def get_repos(hc_home: Path) -> dict:
    """Return the repos section of config (dict of name -> metadata)."""
    return _read(hc_home).get("repos", {})


def add_repo(
    hc_home: Path,
    name: str,
    source: str,
    approval: str = "manual",
    test_cmd: str | None = None,
) -> None:
    """Register a repo in config.

    Args:
        hc_home: Delegate home directory.
        name: Repo name.
        source: Local path or remote URL.
        approval: Merge approval mode — 'auto' or 'manual' (default: 'manual').
        test_cmd: Optional shell command to run tests (e.g. '/path/to/.venv/bin/python -m pytest -x -q').
    """
    data = _read(hc_home)
    repos = data.setdefault("repos", {})
    existing = repos.get(name, {})
    existing["source"] = source
    existing["approval"] = approval
    if test_cmd is not None:
        existing["test_cmd"] = test_cmd
    repos[name] = existing
    _write(hc_home, data)


def update_repo_approval(hc_home: Path, name: str, approval: str) -> None:
    """Update only the approval setting for an existing repo.

    Args:
        hc_home: Delegate home directory.
        name: Repo name (must already exist in config).
        approval: 'auto' or 'manual'.
    """
    data = _read(hc_home)
    repos = data.get("repos", {})
    if name not in repos:
        raise KeyError(f"Repo '{name}' not found in config")
    repos[name]["approval"] = approval
    _write(hc_home, data)


def get_repo_approval(hc_home: Path, repo_name: str) -> str:
    """Return the approval mode for a repo ('auto' or 'manual').

    Defaults to 'manual' if not set or repo not found.
    """
    repos = get_repos(hc_home)
    meta = repos.get(repo_name, {})
    return meta.get("approval", "manual")


# --- Repo test_cmd ---

def get_repo_test_cmd(hc_home: Path, repo_name: str) -> str | None:
    """Return the configured test command for a repo, or None if not set.

    The test command is a shell command string (e.g. '/path/to/.venv/bin/python -m pytest -x -q')
    that should be split with shlex.split() before execution.
    """
    repos = get_repos(hc_home)
    meta = repos.get(repo_name, {})
    return meta.get("test_cmd")


def update_repo_test_cmd(hc_home: Path, name: str, test_cmd: str) -> None:
    """Update the test command for an existing repo.

    Args:
        hc_home: Delegate home directory.
        name: Repo name (must already exist in config).
        test_cmd: Shell command string to run tests.
    """
    data = _read(hc_home)
    repos = data.get("repos", {})
    if name not in repos:
        raise KeyError(f"Repo '{name}' not found in config")
    repos[name]["test_cmd"] = test_cmd
    _write(hc_home, data)


# --- Repo pipeline ---

def get_repo_pipeline(hc_home: Path, repo_name: str) -> list[dict] | None:
    """Return the configured pipeline for a repo, or None if not set.

    If the repo has a ``pipeline`` field, returns it directly as a list of
    ``{name: str, run: str}`` dicts.  If no ``pipeline`` is set but a legacy
    ``test_cmd`` exists, returns a single-step pipeline wrapping it for
    backward compatibility.

    Returns None when neither pipeline nor test_cmd is configured.
    """
    repos = get_repos(hc_home)
    meta = repos.get(repo_name, {})

    pipeline = meta.get("pipeline")
    if pipeline is not None:
        return pipeline

    # Backward compat: wrap legacy test_cmd as a single-step pipeline
    test_cmd = meta.get("test_cmd")
    if test_cmd:
        return [{"name": "test", "run": test_cmd}]

    return None


def set_repo_pipeline(hc_home: Path, name: str, pipeline: list[dict]) -> None:
    """Set the full pipeline for an existing repo.

    Args:
        hc_home: Delegate home directory.
        name: Repo name (must already exist in config).
        pipeline: List of ``{name: str, run: str}`` step dicts.
    """
    data = _read(hc_home)
    repos = data.get("repos", {})
    if name not in repos:
        raise KeyError(f"Repo '{name}' not found in config")
    repos[name]["pipeline"] = pipeline
    _write(hc_home, data)


def add_pipeline_step(hc_home: Path, repo_name: str, step_name: str, run: str) -> None:
    """Append a named step to a repo's pipeline.

    If the repo doesn't have a pipeline yet, creates one.  If it has a
    legacy ``test_cmd`` but no pipeline, migrates the test_cmd into the
    pipeline first.

    Args:
        hc_home: Delegate home directory.
        repo_name: Repo name (must already exist in config).
        step_name: Unique name for the step.
        run: Shell command string for the step.

    Raises:
        KeyError: If the repo doesn't exist.
        ValueError: If a step with the same name already exists.
    """
    data = _read(hc_home)
    repos = data.get("repos", {})
    if repo_name not in repos:
        raise KeyError(f"Repo '{repo_name}' not found in config")

    meta = repos[repo_name]
    pipeline = meta.get("pipeline")

    if pipeline is None:
        # Migrate legacy test_cmd if present
        test_cmd = meta.get("test_cmd")
        if test_cmd:
            pipeline = [{"name": "test", "run": test_cmd}]
        else:
            pipeline = []

    # Check for duplicate step name
    for step in pipeline:
        if step["name"] == step_name:
            raise ValueError(f"Step '{step_name}' already exists in pipeline")

    pipeline.append({"name": step_name, "run": run})
    meta["pipeline"] = pipeline
    _write(hc_home, data)


def remove_pipeline_step(hc_home: Path, repo_name: str, step_name: str) -> None:
    """Remove a named step from a repo's pipeline.

    Args:
        hc_home: Delegate home directory.
        repo_name: Repo name (must already exist in config).
        step_name: Name of the step to remove.

    Raises:
        KeyError: If the repo doesn't exist or the step is not found.
    """
    data = _read(hc_home)
    repos = data.get("repos", {})
    if repo_name not in repos:
        raise KeyError(f"Repo '{repo_name}' not found in config")

    meta = repos[repo_name]
    pipeline = meta.get("pipeline")

    if pipeline is None:
        raise KeyError(f"No pipeline configured for repo '{repo_name}'")

    new_pipeline = [s for s in pipeline if s["name"] != step_name]
    if len(new_pipeline) == len(pipeline):
        raise KeyError(f"Step '{step_name}' not found in pipeline")

    meta["pipeline"] = new_pipeline
    _write(hc_home, data)
