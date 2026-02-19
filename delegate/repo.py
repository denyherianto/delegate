"""Repository management — per-team registration via symlinks and git worktrees.

Registered repos are stored as **symlinks** in
``~/.delegate/teams/<team>/repos/<name>/`` pointing to the real local
repository root.  No clones are made.

Only local repos are supported (the ``.git/`` directory must exist on disk).
If the repo has its own remote, that's fine — delegate doesn't care.

When a repo moves on disk, update the symlink with ``delegate repo update``.

Usage:
    delegate repo add <team> <local_path> [--name NAME]
    delegate repo list <team>
    delegate repo update <team> <name> <new_path>
"""

import json
import logging
import re
import subprocess
from pathlib import Path

from delegate.task import format_task_id

from delegate.paths import repos_dir as _repos_dir, repo_path as _repo_path, task_worktree_dir
from delegate.config import (
    add_repo as _config_add_repo,
    get_repos as _config_get_repos,
    update_repo_approval as _config_update_approval,
    update_repo_test_cmd as _config_update_test_cmd,
)

logger = logging.getLogger(__name__)


def _derive_name(source: str) -> str:
    """Derive a repo name from a local path.

    Examples:
        /Users/me/projects/myapp -> myapp
        /Users/me/dev/standup    -> standup
    """
    source = source.rstrip("/")
    name = source.rsplit("/", 1)[-1]
    name = re.sub(r"[^\w\-.]", "_", name)
    return name or "repo"


def _resolve_repo_dir(hc_home: Path, team: str, name: str) -> Path:
    """Return the canonical repo path (symlink location) inside team/repos/."""
    return _repo_path(hc_home, team, name)


def register_repo(
    hc_home: Path,
    team: str,
    source: str,
    name: str | None = None,
    approval: str | None = None,
    test_cmd: str | None = None,
) -> str:
    """Register a local repository for a team.

    Args:
        hc_home: Delegate home directory.
        team: Team name.
        source: Local path to the repository root (must contain .git/).
        name: Name for the repo (default: derived from source).
        approval: Merge approval mode — 'auto' or 'manual'.
                  Defaults to 'manual' for new repos.
        test_cmd: Optional shell command to run tests.

    Returns:
        The name used for the repo.

    Raises:
        FileNotFoundError: If the source path doesn't exist or has no .git/.
        ValueError: If the source is a remote URL (not supported).
    """
    # Reject remote URLs
    if source.startswith(("http://", "https://", "git@", "ssh://")):
        raise ValueError(
            f"Remote URLs are not supported. Only local paths with .git/ are allowed. Got: {source}"
        )

    source_path = Path(source).resolve()

    if not source_path.is_dir():
        raise FileNotFoundError(f"Repository path not found: {source_path}")

    git_dir = source_path / ".git"
    if not git_dir.exists():
        raise FileNotFoundError(
            f"No .git directory found at {source_path}. "
            "Only local git repositories are supported."
        )

    name = name or _derive_name(source)
    link_path = _resolve_repo_dir(hc_home, team, name)

    if link_path.is_symlink() or link_path.exists():
        # Already registered — update symlink target if different
        current_target = link_path.resolve()
        if current_target != source_path:
            logger.info(
                "Repo '%s' symlink target changed: %s -> %s",
                name, current_target, source_path,
            )
            link_path.unlink()
            link_path.symlink_to(source_path)
        else:
            logger.info("Repo '%s' already registered at %s", name, source_path)

        # Update approval setting if explicitly provided
        if approval is not None:
            _config_update_approval(hc_home, team, name, approval)
            logger.info("Updated approval for '%s' to '%s'", name, approval)

        # Update test_cmd setting if explicitly provided
        if test_cmd is not None:
            _config_update_test_cmd(hc_home, team, name, test_cmd)
            logger.info("Updated test_cmd for '%s'", name)
    else:
        # Create symlink
        link_path.parent.mkdir(parents=True, exist_ok=True)
        link_path.symlink_to(source_path)
        logger.info("Created symlink %s -> %s", link_path, source_path)

        # Register in team config (new repo — default approval to 'manual')
        _config_add_repo(hc_home, team, name, str(source_path), approval=approval or "manual", test_cmd=test_cmd)

    logger.info("Registered repo '%s' for team '%s' from %s", name, team, source_path)
    return name


def update_repo_path(hc_home: Path, team: str, name: str, new_path: str) -> None:
    """Update the symlink for a registered repo to point to a new location.

    Args:
        hc_home: Delegate home directory.
        team: Team name.
        name: Repo name.
        new_path: New local path to the repository root.

    Raises:
        FileNotFoundError: If repo isn't registered or new path doesn't exist.
    """
    link_path = _resolve_repo_dir(hc_home, team, name)
    if not link_path.is_symlink() and not link_path.exists():
        raise FileNotFoundError(f"Repo '{name}' is not registered for team '{team}'")

    new_source = Path(new_path).resolve()
    if not new_source.is_dir():
        raise FileNotFoundError(f"New path not found: {new_source}")
    if not (new_source / ".git").exists():
        raise FileNotFoundError(f"No .git directory at {new_source}")

    if link_path.is_symlink():
        link_path.unlink()
    link_path.symlink_to(new_source)

    # Update team config
    from delegate.config import _read_repos, _write_repos
    data = _read_repos(hc_home, team)
    if name in data:
        data[name]["source"] = str(new_source)
        _write_repos(hc_home, team, data)

    logger.info("Updated repo '%s' symlink -> %s", name, new_source)


def list_repos(hc_home: Path, team: str) -> dict:
    """List registered repos for a team from config.

    Returns:
        Dict of name -> metadata (source, approval, etc.).
    """
    return _config_get_repos(hc_home, team)


def get_repo_path(hc_home: Path, team: str, repo_name: str) -> Path:
    """Get the canonical path to a repo (the symlink in team/repos/).

    The symlink resolves to the real repo root on disk.
    """
    return _resolve_repo_dir(hc_home, team, repo_name)


# Keep old name as alias for compatibility
get_repo_clone_path = get_repo_path


def _get_main_head(repo_dir: Path) -> str:
    """Get the current HEAD SHA of the main branch in a repo."""
    result = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


_SCRIPT_HEADER = """\
#!/usr/bin/env bash
set -e
# Auto-generated by delegate at worktree creation. Edit as needed.
"""

_SETUP_SCRIPT_NAME = ".delegate.setup.sh"
_TEST_SCRIPT_NAME = ".delegate.test.sh"


def _has_cmd(cmd: str) -> bool:
    """Return True if a command is available on PATH."""
    result = subprocess.run(
        ["which", cmd],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _node_package_manager(root: Path) -> str:
    """Return the node package manager install command for a given directory."""
    if (root / "pnpm-lock.yaml").exists():
        if _has_cmd("pnpm"):
            return "pnpm install"
        return "npm ci  # pnpm-lock.yaml found but pnpm not available — using npm"
    if (root / "yarn.lock").exists():
        if _has_cmd("yarn"):
            return "yarn install"
        return "npm ci  # yarn.lock found but yarn not available — using npm"
    return "npm ci"


def _has_npm_test_script(root: Path) -> bool:
    """Return True if package.json has a 'test' script."""
    pkg = root / "package.json"
    if not pkg.exists():
        return False
    try:
        data = json.loads(pkg.read_text())
        return "test" in data.get("scripts", {})
    except Exception:
        return False


def _python_setup_cmd(root: Path) -> str:
    """Return setup commands for Python stack at root."""
    if _has_cmd("uv"):
        if (root / "pyproject.toml").exists():
            return "uv venv && uv pip install -e \".[dev]\" && source .venv/bin/activate"
        else:
            return "uv venv && uv pip install -r requirements.txt && source .venv/bin/activate"
    else:
        if (root / "pyproject.toml").exists():
            return "python -m venv .venv && pip install -e \".[dev]\" && source .venv/bin/activate"
        else:
            return "python -m venv .venv && pip install -r requirements.txt && source .venv/bin/activate"


def _detect_stack(root: Path) -> list[dict]:
    """Detect all stacks at root (and one level of subdirs).

    Returns a list of dicts with keys:
        label: str  — human-readable label for comment (e.g. "Python", "Node (frontend/)")
        setup: str  — setup commands (may be multi-line)
        test: str   — test command
        subdir: str | None  — relative subdir path if not root
    """
    stacks = []

    def _check_dir(d: Path, subdir: str | None) -> None:
        """Detect stacks in directory d (relative path subdir for labelling)."""
        label_suffix = f" ({subdir}/)" if subdir else ""

        # Python: pyproject.toml
        if (d / "pyproject.toml").exists():
            stacks.append({
                "label": f"Python{label_suffix}",
                "setup": _python_setup_cmd(d),
                "test": "pytest",
                "subdir": subdir,
            })
        elif (d / "requirements.txt").exists():
            # requirements.txt but no pyproject.toml
            stacks.append({
                "label": f"Python{label_suffix}",
                "setup": _python_setup_cmd(d),
                "test": "pytest",
                "subdir": subdir,
            })

        # JavaScript / TypeScript: package.json
        if (d / "package.json").exists():
            pkg_mgr = _node_package_manager(d)
            lang = "TypeScript" if (d / "tsconfig.json").exists() else "JavaScript"
            if _has_npm_test_script(d):
                test_cmd = "npm test"
            else:
                test_cmd = "echo 'No tests configured'; exit 0"
            stacks.append({
                "label": f"{lang}{label_suffix}",
                "setup": f"{pkg_mgr} && export PATH=\"$PWD/node_modules/.bin:$PATH\"",
                "test": test_cmd,
                "subdir": subdir,
            })

        # Rust
        if (d / "Cargo.toml").exists():
            stacks.append({
                "label": f"Rust{label_suffix}",
                "setup": "cargo build",
                "test": "cargo test",
                "subdir": subdir,
            })

        # Go
        if (d / "go.mod").exists():
            stacks.append({
                "label": f"Go{label_suffix}",
                "setup": "go mod tidy",
                "test": "go test ./...",
                "subdir": subdir,
            })

        # Java (Maven)
        if (d / "pom.xml").exists():
            mvn_setup = "./mvnw dependency:resolve -q" if (d / "mvnw").exists() else "mvn dependency:resolve -q"
            mvn_test = "./mvnw test -q" if (d / "mvnw").exists() else "mvn test -q"
            stacks.append({
                "label": f"Java (Maven){label_suffix}",
                "setup": mvn_setup,
                "test": mvn_test,
                "subdir": subdir,
            })

        # Java (Gradle)
        if (d / "build.gradle").exists() or (d / "build.gradle.kts").exists():
            gradle_setup = "./gradlew dependencies -q" if (d / "gradlew").exists() else "gradle dependencies -q"
            gradle_test = "./gradlew test" if (d / "gradlew").exists() else "gradle test"
            stacks.append({
                "label": f"Java (Gradle){label_suffix}",
                "setup": gradle_setup,
                "test": gradle_test,
                "subdir": subdir,
            })

        # C# (.csproj or .sln)
        csproj_files = list(d.glob("*.csproj")) + list(d.glob("*.sln"))
        if csproj_files:
            stacks.append({
                "label": f"C#{label_suffix}",
                "setup": "dotnet restore",
                "test": "dotnet test",
                "subdir": subdir,
            })

        # Swift
        if (d / "Package.swift").exists():
            stacks.append({
                "label": f"Swift{label_suffix}",
                "setup": "swift package resolve",
                "test": "swift test",
                "subdir": subdir,
            })

        # Ruby
        if (d / "Gemfile").exists():
            stacks.append({
                "label": f"Ruby{label_suffix}",
                "setup": "bundle install",
                "test": "bundle exec rspec",
                "subdir": subdir,
            })

        # C/C++ (CMake)
        if (d / "CMakeLists.txt").exists():
            stacks.append({
                "label": f"C/C++ (CMake){label_suffix}",
                "setup": "cmake -B build && cmake --build build",
                "test": "cd build && ctest",
                "subdir": subdir,
            })
        elif (d / "Makefile").exists():
            # C/C++ (Make) — no reliable setup target
            stacks.append({
                "label": f"C/C++ (Make){label_suffix}",
                "setup": "",  # no reliable deps target
                "test": "make test",
                "subdir": subdir,
            })

    # Check root
    _check_dir(root, None)

    # Check one level of subdirectories
    try:
        for entry in sorted(root.iterdir()):
            if entry.is_dir() and not entry.name.startswith(".") and entry.name != "node_modules":
                _check_dir(entry, entry.name)
    except PermissionError:
        pass

    return stacks


def _mine_dockerfile(root: Path) -> list[dict]:
    """Mine Dockerfile for stack clues and return detected stacks."""
    dockerfile = root / "Dockerfile"
    if not dockerfile.exists():
        return []

    text = dockerfile.read_text(errors="replace")
    stacks = []
    comment = "# Inferred from Dockerfile -- review and edit as needed"

    if re.search(r"FROM python:|RUN pip install", text):
        stacks.append({
            "label": "Python (Dockerfile)",
            "setup": f"{comment}\n" + _python_setup_cmd(root),
            "test": "pytest",
            "subdir": None,
        })
    if re.search(r"FROM node:|RUN npm install", text):
        stacks.append({
            "label": "Node (Dockerfile)",
            "setup": f"{comment}\nnpm ci && export PATH=\"$PWD/node_modules/.bin:$PATH\"",
            "test": "npm test",
            "subdir": None,
        })
    if re.search(r"FROM rust:|RUN cargo build", text):
        stacks.append({
            "label": "Rust (Dockerfile)",
            "setup": f"{comment}\ncargo build",
            "test": "cargo test",
            "subdir": None,
        })
    return stacks


def _build_script_body(stacks: list[dict], script_type: str) -> str:
    """Build the body (after header) of a setup or test script from detected stacks.

    script_type: 'setup' or 'test'
    """
    if not stacks:
        return "# No stack detected. Fill in setup and test commands for this repo.\n"

    parts = []
    for s in stacks:
        label = s["label"]
        cmd = s["setup"] if script_type == "setup" else s["test"]
        subdir = s["subdir"]

        # Skip sections with empty setup commands (e.g. C/C++ Make)
        if script_type == "setup" and not cmd:
            continue

        if subdir:
            # Wrap in subshell to avoid changing working directory
            if "\n" in cmd:
                # Multi-line: wrap each line in subshell context
                inner = cmd.replace("\n", "\n    ")
                parts.append(f"# {label}\n(cd {subdir} && {inner})")
            else:
                parts.append(f"# {label}\n(cd {subdir} && {cmd})")
        else:
            parts.append(f"# {label}\n{cmd}")

    if not parts:
        return "# No setup commands detected. Fill in as needed.\n"
    return "\n\n".join(parts) + "\n"


def generate_env_scripts(repo_path: Path) -> tuple[bool, bool]:
    """Generate .delegate.setup.sh and .delegate.test.sh in repo_path if absent.

    Detects the stack using heuristics and writes appropriate scripts.

    Priority order:
      1. Scripts already exist -> skip entirely
      2. flake.nix or shell.nix present -> Nix-based scripts
      3. Standard indicator files -> heuristic detection (all matches)
      4. Dockerfile only -> mine for stack clues
      5. Nothing -> empty scripts with comment

    Returns:
        (setup_written, test_written) — True if each file was written (new or
        existing skipped returns (False, False)).
    """
    setup_path = repo_path / _SETUP_SCRIPT_NAME
    test_path = repo_path / _TEST_SCRIPT_NAME

    # Priority 1: scripts already exist — skip entirely
    if setup_path.exists():
        logger.info("Env scripts already exist in %s — skipping generation", repo_path)
        return False, False

    setup_lines = [_SCRIPT_HEADER]
    test_lines = [_SCRIPT_HEADER]

    # Priority 2: Nix
    has_flake = (repo_path / "flake.nix").exists()
    has_shell = (repo_path / "shell.nix").exists()
    if has_flake or has_shell:
        if _has_cmd("nix"):
            if has_flake:
                setup_lines.append(
                    "# Nix flake environment\n"
                    "nix develop --command bash -c \"echo 'Nix environment activated'\"\n"
                    "# To run commands in the nix env: nix develop --command <cmd>\n"
                )
                test_lines.append(
                    "# Nix flake environment\n"
                    "nix develop --command pytest\n"
                )
            else:
                setup_lines.append(
                    "# Nix shell environment\n"
                    "nix-shell --run \"echo 'Nix environment activated'\"\n"
                    "# To run commands in the nix env: nix-shell --run '<cmd>'\n"
                )
                test_lines.append(
                    "# Nix shell environment\n"
                    "nix-shell --run pytest\n"
                )
        else:
            nix_file = "flake.nix" if has_flake else "shell.nix"
            setup_lines.append(
                f"# WARNING: {nix_file} found but nix is not installed.\n"
                "# Install nix from https://nixos.org/download/ then re-run delegate repo add.\n"
                "# Falling back to heuristic detection:\n"
            )
            test_lines.append(
                f"# WARNING: {nix_file} found but nix is not installed.\n"
                "# Falling back to heuristic detection:\n"
            )
            # Fall through to heuristic detection below
            has_flake = has_shell = False  # so we enter the heuristic block

    if not has_flake and not has_shell:
        # Priority 3: standard indicator heuristics
        stacks = _detect_stack(repo_path)

        if stacks:
            setup_lines.append(_build_script_body(stacks, "setup"))
            test_lines.append(_build_script_body(stacks, "test"))
        else:
            # Priority 4: Dockerfile mining
            docker_stacks = _mine_dockerfile(repo_path)
            if docker_stacks:
                setup_lines.append(_build_script_body(docker_stacks, "setup"))
                test_lines.append(_build_script_body(docker_stacks, "test"))
            else:
                # Priority 5: nothing detected
                no_detect = "# No stack detected. Fill in setup and test commands for this repo.\n"
                setup_lines.append(no_detect)
                test_lines.append(no_detect)

    setup_content = "\n".join(setup_lines)
    test_content = "\n".join(test_lines)

    setup_path.write_text(setup_content)
    setup_path.chmod(0o755)
    logger.info("Wrote %s", setup_path)

    test_path.write_text(test_content)
    test_path.chmod(0o755)
    logger.info("Wrote %s", test_path)

    return True, True


def create_task_worktree(
    hc_home: Path,
    team: str,
    repo_name: str,
    task_id: int,
    branch: str | None = None,
) -> Path:
    """Create a git worktree for a task.

    The worktree lives at ``teams/{team}/worktrees/{repo_name}/T{task_id}/``
    (one per task+repo, shared by all agents working on the task).

    Before creating the branch, fetches the latest from origin (if available)
    and records the base SHA (current main HEAD) on the task.

    Args:
        hc_home: Delegate home directory.
        team: Team name.
        repo_name: Name of the registered repo.
        task_id: Task ID number.
        branch: Branch name (default: delegate/<team>/T<task_id>).

    Returns:
        Path to the created worktree directory.

    Raises:
        FileNotFoundError: If the repo isn't registered.
        subprocess.CalledProcessError: If git worktree add fails.
    """
    repo_dir = get_repo_path(hc_home, team, repo_name)
    real_repo = repo_dir.resolve()
    if not real_repo.is_dir():
        raise FileNotFoundError(f"Repo not found at {real_repo} (symlink: {repo_dir})")

    # Default branch name
    if branch is None:
        from delegate.paths import get_team_id
        tid = get_team_id(hc_home, team)
        branch = f"delegate/{tid}/{team}/{format_task_id(task_id)}"

    # Worktree destination (task-scoped)
    wt_path = task_worktree_dir(hc_home, team, repo_name, task_id)

    if wt_path.exists():
        # Worktree exists — still backfill base_sha if missing on the task
        try:
            from delegate.task import get_task as _get_task, update_task as _update_task
            task = _get_task(hc_home, team, task_id)
            existing_base: dict = task.get("base_sha", {})
            if not existing_base or repo_name not in existing_base:
                sha = _get_main_head(real_repo)
                new_base = {**existing_base, repo_name: sha}
                _update_task(hc_home, team, task_id, base_sha=new_base)
                logger.info("Backfilled base_sha[%s]=%s for existing worktree %s", repo_name, sha[:8], task_id)
        except Exception as exc:
            logger.warning("Could not backfill base_sha for %s: %s", task_id, exc)
        logger.info("Worktree already exists at %s", wt_path)
        return wt_path

    wt_path.parent.mkdir(parents=True, exist_ok=True)

    # Fetch latest before creating worktree (best effort)
    subprocess.run(
        ["git", "fetch", "--all"],
        cwd=str(real_repo),
        capture_output=True,
        check=False,  # Don't fail if fetch fails (offline, no remote)
    )

    # Record base SHA (current main HEAD) on the task (per-repo dict)
    try:
        sha = _get_main_head(real_repo)
        from delegate.task import get_task as _gt, update_task as _ut
        existing_task = _gt(hc_home, team, task_id)
        existing_base: dict = existing_task.get("base_sha", {})
        new_base = {**existing_base, repo_name: sha}
        _ut(hc_home, team, task_id, base_sha=new_base)
        logger.info("Recorded base_sha[%s]=%s for %s", repo_name, sha[:8], task_id)
    except Exception as exc:
        logger.warning("Could not record base_sha for %s: %s", task_id, exc)

    # Defensive prune to clean up any stale worktree metadata before creating
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=str(real_repo),
        capture_output=True,
        check=False,
    )

    # Create worktree with a new branch off main
    subprocess.run(
        ["git", "worktree", "add", str(wt_path), "-b", branch, "main"],
        cwd=str(real_repo),
        capture_output=True,
        check=True,
    )

    logger.info("Created worktree at %s (branch: %s)", wt_path, branch)

    # Generate env scripts if not already present.
    # Only the first agent to get a worktree will write them; subsequent worktrees
    # inherit the scripts from main after the first merge.
    try:
        generate_env_scripts(wt_path)
    except Exception as exc:
        logger.warning("Could not generate env scripts for %s: %s", wt_path, exc)

    return wt_path


def remove_task_worktree(
    hc_home: Path,
    team: str,
    repo_name: str,
    task_id: int,
) -> None:
    """Remove the worktree for a task.

    Args:
        hc_home: Delegate home directory.
        team: Team name.
        repo_name: Name of the registered repo.
        task_id: Task ID number.
    """
    repo_dir = get_repo_path(hc_home, team, repo_name)
    real_repo = repo_dir.resolve()
    wt_path = task_worktree_dir(hc_home, team, repo_name, task_id)

    # Remove worktree via git if directory exists
    if wt_path.exists():
        if real_repo.is_dir():
            subprocess.run(
                ["git", "worktree", "remove", str(wt_path), "--force"],
                cwd=str(real_repo),
                capture_output=True,
                check=False,
            )
        else:
            # Repo gone — just remove directory
            import shutil
            shutil.rmtree(wt_path, ignore_errors=True)
        logger.info("Removed worktree at %s", wt_path)
    else:
        logger.info("Worktree already removed: %s", wt_path)

    # Always prune stale worktree entries, even if directory was already gone
    # This cleans up orphaned git metadata that blocks future worktree creation
    if real_repo.is_dir():
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(real_repo),
            capture_output=True,
            check=False,
        )


def get_task_worktree_path(
    hc_home: Path,
    team: str,
    repo_name: str,
    task_id: int,
) -> Path:
    """Get the path to a task's worktree.

    Returns the path even if the worktree doesn't exist yet.
    """
    return task_worktree_dir(hc_home, team, repo_name, task_id)


# ---------------------------------------------------------------------------
# Legacy wrappers (thin compatibility shims)
# ---------------------------------------------------------------------------

def create_agent_worktree(
    hc_home: Path,
    team: str,
    repo_name: str,
    agent: str,
    task_id: int,
    branch: str | None = None,
) -> Path:
    """Legacy wrapper — delegates to ``create_task_worktree``."""
    return create_task_worktree(hc_home, team, repo_name, task_id, branch=branch)


def remove_agent_worktree(
    hc_home: Path,
    team: str,
    repo_name: str,
    agent: str,
    task_id: int,
) -> None:
    """Legacy wrapper — delegates to ``remove_task_worktree``."""
    remove_task_worktree(hc_home, team, repo_name, task_id)


def get_worktree_path(
    hc_home: Path,
    team: str,
    repo_name: str,
    agent: str,
    task_id: int,
) -> Path:
    """Legacy wrapper — delegates to ``get_task_worktree_path``."""
    return get_task_worktree_path(hc_home, team, repo_name, task_id)


def push_branch(
    hc_home: Path,
    team: str,
    repo_name: str,
    branch: str,
    remote: str = "origin",
) -> bool:
    """Push a branch to the remote.

    Uses the real repo (via symlink) as the working directory.

    Returns:
        True if push succeeded, False otherwise.
    """
    repo_dir = get_repo_path(hc_home, team, repo_name)
    real_repo = repo_dir.resolve()
    if not real_repo.is_dir():
        logger.error("Repo not found: %s", real_repo)
        return False

    result = subprocess.run(
        ["git", "push", remote, branch],
        cwd=str(real_repo),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("Push failed: %s", result.stderr)
        return False

    logger.info("Pushed branch '%s' to %s", branch, remote)
    return True
