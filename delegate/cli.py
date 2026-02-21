"""Delegate CLI entry point using Click.

Commands:
    delegate doctor                                  — verify runtime dependencies
    delegate start [--port N] [--env-file .env]       — start delegate (web UI + agents)
    delegate stop                                    — stop running delegate
    delegate status                                  — check if delegate is running
    delegate team add <name> --agents a:role,b --repo /path  — create a new team
    delegate team list                               — list existing teams
    delegate team remove <name>                      — remove a team and all its data
    delegate agent add <team> <name>                 — add an agent to a team
    delegate config set human <name>                 — set the human member name
    delegate config set boss <name>                  — (deprecated) alias for 'config set human'
    delegate config set source-repo <path>           — set delegate source repo path
    delegate repo add <team> <path_or_url> [--name]  — register a repository for a team
    delegate repo list <team>                        — list repos for a team
    delegate workflow add <team> <path>              — register a workflow for a team
    delegate workflow list <team>                    — list workflows for a team
    delegate workflow show <team> <name>             — show workflow details/graph
    delegate workflow update-actions <team> <name> <path> — update workflow actions
    delegate workflow init <team>                    — register built-in default workflow
    delegate self-update                             — update delegate from source repo
    delegate nuke                                    — destroy all delegate state (requires confirmation)
"""

import platform
import subprocess
import sys
from pathlib import Path

import click

from delegate.fmt import get_version
from delegate.paths import home as _home, teams_dir as _teams_dir, team_dir as _team_dir


def _get_home(ctx: click.Context) -> Path:
    """Resolve delegate home from context or default."""
    return _home(ctx.obj.get("home_override") if ctx.obj else None)


@click.group()
@click.version_option(version=get_version(), prog_name="delegate")
@click.option(
    "--home", "home_override", type=click.Path(path_type=Path), default=None,
    envvar="DELEGATE_HOME",
    help="Override delegate home directory (default: ~/.delegate).",
)
@click.pass_context
def main(ctx: click.Context, home_override: Path | None) -> None:
    """Delegate — agentic team management system."""
    ctx.ensure_object(dict)
    ctx.obj["home_override"] = home_override


# ──────────────────────────────────────────────────────────────
# delegate doctor
# ──────────────────────────────────────────────────────────────

@main.command()
def doctor() -> None:
    """Verify that all runtime dependencies are installed."""
    from delegate.doctor import run_doctor, print_doctor_report

    checks = run_doctor()
    ok = print_doctor_report(checks)
    if not ok:
        raise SystemExit(1)


# ──────────────────────────────────────────────────────────────
# delegate start / stop / status
# ──────────────────────────────────────────────────────────────

DEFAULT_PORT = 3548


def _open_ui(url: str, port: int) -> None:
    """Try to open the PWA (macOS); fall back to browser."""
    import webbrowser

    if platform.system() == "Darwin":
        app_name = "Delegate" if port == DEFAULT_PORT else f"Delegate :{port}"
        try:
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return  # PWA opened successfully
        except (subprocess.TimeoutExpired, OSError):
            pass
    # Fallback: open in browser
    try:
        webbrowser.open(url)
    except Exception:
        pass


@main.command()
@click.option("--port", type=int, default=3548, help="Port for the web UI (default: 3548).")
@click.option("--interval", type=float, default=1.0, help="Poll interval in seconds.")
@click.option("--max-concurrent", type=int, default=32, help="Max concurrent agents.")
@click.option("--token-budget", type=int, default=None, help="Default token budget per agent session.")
@click.option("--foreground", is_flag=True, help="Run in foreground instead of background.")
@click.option(
    "--env-file", type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to .env file to load (e.g. for ANTHROPIC_API_KEY).",
)
@click.option("--dev", is_flag=True, help="Enable dev mode (esbuild watcher for live frontend rebuilds).")
@click.option("--skip-auth-check", is_flag=True, help="Skip Claude CLI/API key checks (useful for enterprise auth setups).")
@click.pass_context
def start(
    ctx: click.Context,
    port: int,
    interval: float,
    max_concurrent: int,
    token_budget: int | None,
    foreground: bool,
    env_file: Path | None,
    dev: bool,
    skip_auth_check: bool,
) -> None:
    """Start delegate (web UI + agent orchestration)."""
    import time
    from delegate.daemon import start_daemon, is_running
    from delegate.doctor import run_doctor, print_doctor_report
    from delegate.fmt import success, get_auth_display, get_version

    # Load env file if provided — makes vars available to this process
    # and all child processes (daemon, agents).
    if env_file:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        success(f"Loaded env file: {env_file}")

    hc_home = _get_home(ctx)

    # Migrate legacy boss config → members/ (one-time)
    from delegate.config import migrate_boss_to_member, migrate_standard_to_default_workflow
    migrated = migrate_boss_to_member(hc_home)
    if migrated:
        success(f"Migrated legacy boss '{migrated}' to members/")

    # Migrate standard → default workflow (one-time)
    wf_migrated = migrate_standard_to_default_workflow(hc_home)
    if wf_migrated:
        success(f"Migrated {wf_migrated} team(s) from 'standard' to 'default' workflow")

    # Run doctor check first — suppress output if all checks pass
    checks = run_doctor(skip_auth=skip_auth_check)
    all_ok = all(c.passed for c in checks)
    if not all_ok:
        print_doctor_report(checks)
        raise SystemExit(1)

    # Show version and auth method
    click.echo(f"Delegate v{get_version()}")
    click.echo()
    auth_display = get_auth_display()
    success(f"Auth: {auth_display}")

    url = f"http://localhost:{port}"

    alive, pid = is_running(hc_home)
    if alive:
        success(f"Delegate already running (PID {pid})")
        success(f"UI: {url}")
        # Server is up — open browser immediately regardless of --foreground
        _open_ui(url, port)
        return

    success(f"Starting delegate on port {port}...")

    if foreground:
        # foreground blocks forever; open browser from a background thread
        # after a short delay to let the server bind
        import threading

        def _open_browser() -> None:
            time.sleep(2)
            _open_ui(url, port)

        threading.Thread(target=_open_browser, daemon=True).start()

        start_daemon(
            hc_home,
            port=port,
            interval=interval,
            max_concurrent=max_concurrent,
            token_budget=token_budget,
            foreground=True,
            dev=dev,
        )
    else:
        result_pid = start_daemon(
            hc_home,
            port=port,
            interval=interval,
            max_concurrent=max_concurrent,
            token_budget=token_budget,
            foreground=False,
            dev=dev,
        )
        if result_pid:
            success(f"Delegate started (PID {result_pid})")
        else:
            success("Delegate started")

        success(f"UI: {url}")

        time.sleep(1.5)
        _open_ui(url, port)


@main.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    """Stop the running delegate."""
    from delegate.daemon import stop_daemon, is_running
    from delegate.fmt import success, warn, info

    hc_home = _get_home(ctx)
    alive, _ = is_running(hc_home)
    if not alive:
        warn("Delegate is not running")
        return

    info("Stopping delegate...")
    stopped = stop_daemon(hc_home)
    if stopped:
        success("Delegate stopped")


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Check if delegate is running."""
    from delegate.daemon import is_running
    from delegate.fmt import success, info

    hc_home = _get_home(ctx)
    alive, pid = is_running(hc_home)
    if alive:
        success(f"Delegate running (PID {pid})")
    else:
        info("Delegate not running")


# ──────────────────────────────────────────────────────────────
# delegate team add / list / remove
# ──────────────────────────────────────────────────────────────

@main.group()
def team() -> None:
    """Manage teams."""
    pass


@team.command("add")
@click.argument("name")
@click.option(
    "--agents", required=True,
    help="Number of agents (e.g. '3') or comma-separated names as name[:role].  "
         "Examples: '3', 'alex:devops,nikhil:designer,john,mark:backend'.  "
         "Numeric values auto-generate names (agent-1, agent-2, ...).  "
         "Agents without a role default to 'engineer'.",
)
@click.option(
    "--repo", "repos", required=True, multiple=True,
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Local repo path(s) for the team.  Repeat for multiple repos: --repo /path/a --repo /path/b",
)
@click.option("--interactive", is_flag=True, help="Prompt for bios and charter overrides.")
@click.option(
    "--model", default=None,
    help="Model assignment. Either a single model ('opus' or 'sonnet') to apply to all agents, "
         "or comma-separated name:model pairs (e.g. 'alice:opus,bob:sonnet'). "
         "Defaults to sonnet for all roles.",
)
@click.pass_context
def team_create(
    ctx: click.Context,
    name: str,
    agents: str,
    repos: tuple[str, ...],
    interactive: bool,
    model: str | None,
) -> None:
    """Create a new team."""
    from delegate.bootstrap import bootstrap, validate_project_name
    from delegate.repo import register_repo
    from delegate.fmt import success, warn

    hc_home = _get_home(ctx)

    # Validate team name before doing any work
    try:
        validate_project_name(name)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    # Parse agents: either a count or "name:role" pairs
    parsed_agents: list[tuple[str, str]] = []
    agents_stripped = agents.strip()
    if agents_stripped.isdigit():
        # Numeric: pick random names from pool
        count = int(agents_stripped)
        from delegate.names import pick_names
        from delegate.config import get_default_human
        from delegate.runtime import list_ai_agents
        from delegate.paths import teams_dir

        # Exclude human member name, manager name, and all existing agent names
        exclude = set()
        human_name = get_default_human(hc_home)
        if human_name:
            exclude.add(human_name)
        exclude.add("delegate")

        # Collect all existing agent names across all teams
        tdir = teams_dir(hc_home)
        if tdir.is_dir():
            for team_path in tdir.iterdir():
                if team_path.is_dir():
                    team_name = team_path.name
                    agent_names = list_ai_agents(hc_home, team_name)
                    exclude.update(agent_names)

        chosen = pick_names(count, exclude)
        for agent_name in chosen:
            parsed_agents.append((agent_name, "engineer"))
    else:
        # Parse "name:role" pairs — role defaults to "engineer"
        for token in agents_stripped.split(","):
            token = token.strip()
            if not token:
                continue
            if ":" in token:
                agent_name, role = token.split(":", 1)
                parsed_agents.append((agent_name.strip(), role.strip()))
            else:
                parsed_agents.append((token, "engineer"))

    # Parse --model option into a models dict for bootstrap
    # Formats: "opus" (all agents), or "alice:opus,bob:sonnet" (per-agent)
    models_dict: dict[str, str] | None = None
    if model is not None:
        valid_models = ("opus", "sonnet")
        model_stripped = model.strip()
        if model_stripped in valid_models:
            # Single model applies to all agents via wildcard key
            models_dict = {"*": model_stripped}
        elif ":" in model_stripped:
            # Per-agent name:model pairs
            models_dict = {}
            for token in model_stripped.split(","):
                token = token.strip()
                if not token:
                    continue
                if ":" not in token:
                    raise click.ClickException(
                        f"Invalid --model format '{token}'. Use 'opus', 'sonnet', or 'name:model' pairs."
                    )
                agent_name, agent_model = token.split(":", 1)
                agent_name = agent_name.strip()
                agent_model = agent_model.strip()
                if agent_model not in valid_models:
                    raise click.ClickException(
                        f"Invalid model '{agent_model}' for agent '{agent_name}'. Must be 'opus' or 'sonnet'."
                    )
                models_dict[agent_name] = agent_model
        else:
            raise click.ClickException(
                f"Invalid --model value '{model_stripped}'. Use 'opus', 'sonnet', or 'name:model' pairs."
            )

    bootstrap(
        hc_home,
        team_name=name,
        manager="delegate",
        agents=parsed_agents,
        interactive=interactive,
        models=models_dict,
    )

    success(f"Created team '{name}'")

    # Register the built-in default workflow
    try:
        from delegate.workflow import register_workflow, get_latest_version
        builtin = Path(__file__).parent / "workflows" / "default.py"
        if builtin.is_file() and get_latest_version(hc_home, name, "default") is None:
            register_workflow(hc_home, name, builtin)
            success("Registered default workflow: default v1")
    except Exception as exc:
        from delegate.fmt import warn
        warn(f"Could not register default workflow: {exc}")

    # Register repos
    registered: list[str] = []
    for repo_path in repos:
        try:
            repo_name = register_repo(hc_home, name, repo_path)
            registered.append(repo_name)
            success(f"Registered repo: {repo_name}")
        except (FileNotFoundError, ValueError) as exc:
            warn(f"Could not register repo '{repo_path}': {exc}")

    # Show team members
    labels = ["delegate (manager)"]
    for aname, arole in parsed_agents:
        labels.append(f"{aname} ({arole})" if arole != "engineer" else aname)
    success(f"Members: {', '.join(labels)}")


@team.command("list")
@click.pass_context
def team_list(ctx: click.Context) -> None:
    """List all teams."""
    hc_home = _get_home(ctx)
    td = _teams_dir(hc_home)
    if not td.is_dir():
        click.echo("No teams found.")
        return

    teams = sorted(d.name for d in td.iterdir() if d.is_dir())
    if not teams:
        click.echo("No teams found.")
        return

    click.echo("Teams:")
    for t in teams:
        click.echo(f"  - {click.style(t, bold=True)}")


@team.command("remove")
@click.argument("name")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def team_remove(ctx: click.Context, name: str, yes: bool) -> None:
    """Remove a team and all its data.

    This deletes the team directory (agents, worktrees, DB, repos config)
    permanently.  It does NOT delete the actual git repositories — only the
    symlinks/config that Delegate created.
    """
    import shutil
    from delegate.fmt import success

    hc_home = _get_home(ctx)
    td = _team_dir(hc_home, name)
    if not td.is_dir():
        click.echo(f"Team '{name}' does not exist.")
        raise SystemExit(1)

    if not yes:
        click.confirm(
            f"Remove team '{name}' and all its data? This cannot be undone.",
            abort=True,
        )

    shutil.rmtree(td)

    # Remove from global teams database table
    try:
        from delegate.db import get_connection
        conn = get_connection(hc_home, "")
        try:
            conn.execute("DELETE FROM projects WHERE name = ?", (name,))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # Best-effort — directory is already gone

    success(f"Removed team '{name}'")


# ──────────────────────────────────────────────────────────────
# delegate agent add
# ──────────────────────────────────────────────────────────────

@main.group()
def agent() -> None:
    """Manage agents on a team."""
    pass


@agent.command("add")
@click.argument("team")
@click.argument("name", required=False, default=None)
@click.option(
    "--role", default="engineer",
    help="Role for the new agent (default: engineer).",
)
@click.option(
    "--model", default=None, type=click.Choice(["opus", "sonnet"]),
    help="Model: opus or sonnet. Default: sonnet for all roles.",
)
@click.option(
    "--bio", default=None,
    help="Short bio/description of the agent's strengths and focus.",
)
@click.pass_context
def agent_add(ctx: click.Context, team: str, name: str | None, role: str, model: str, bio: str | None) -> None:
    """Add a new agent to an existing team.

    TEAM is the team name.  NAME is the new agent's name (optional - auto-generated if omitted).
    """
    from delegate.bootstrap import add_agent
    from delegate.fmt import success

    hc_home = _get_home(ctx)
    try:
        agent_name = add_agent(hc_home, team_name=team, agent_name=name, role=role, model=model, bio=bio)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))

    resolved_model = model or "sonnet"
    success(f"Added agent '{agent_name}' to team '{team}' (role: {role}, model: {resolved_model})")


# ──────────────────────────────────────────────────────────────
# delegate member add / list / remove
# ──────────────────────────────────────────────────────────────

@main.group()
def member() -> None:
    """Manage human members."""
    pass


@member.command("add")
@click.argument("name")
@click.pass_context
def member_add(ctx: click.Context, name: str) -> None:
    """Add a human member to Delegate.

    Creates a member YAML file in ~/.delegate/members/.
    The member is automatically added to all existing teams' rosters.
    """
    from delegate.config import add_member
    from delegate.fmt import success

    hc_home = _get_home(ctx)
    add_member(hc_home, name)
    success(f"Added member '{name}'")

    # Auto-add to all existing teams' rosters
    td = _teams_dir(hc_home)
    if td.is_dir():
        from delegate.paths import roster_path as _roster_path
        for team_dir in sorted(td.iterdir()):
            if not team_dir.is_dir():
                continue
            rp = _roster_path(hc_home, team_dir.name)
            if rp.exists():
                roster_text = rp.read_text()
                roster_line = f"- **{name}** (member)"
                if roster_line not in roster_text:
                    if not roster_text.endswith("\n"):
                        roster_text += "\n"
                    roster_text += roster_line + "\n"
                    rp.write_text(roster_text)
                    success(f"  Added to team '{team_dir.name}'")


@member.command("list")
@click.pass_context
def member_list(ctx: click.Context) -> None:
    """List all human members."""
    from delegate.config import get_human_members

    hc_home = _get_home(ctx)
    members = get_human_members(hc_home)
    if not members:
        click.echo("No members found.")
        return

    click.echo("Members:")
    for m in members:
        click.echo(f"  - {click.style(m['name'], bold=True)} (kind: {m.get('kind', 'human')})")


@member.command("remove")
@click.argument("name")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def member_remove(ctx: click.Context, name: str, yes: bool) -> None:
    """Remove a human member."""
    from delegate.config import remove_member
    from delegate.fmt import success

    hc_home = _get_home(ctx)
    if not yes:
        click.confirm(f"Remove member '{name}'?", abort=True)

    if remove_member(hc_home, name):
        success(f"Removed member '{name}'")
    else:
        click.echo(f"Member '{name}' not found.")


# ──────────────────────────────────────────────────────────────
# delegate config set human / boss / source-repo
# ──────────────────────────────────────────────────────────────

@main.group()
def config() -> None:
    """Manage org-wide configuration."""
    pass


@config.group("set")
def config_set() -> None:
    """Set a configuration value."""
    pass


def _set_human_name(hc_home: Path, name: str) -> None:
    """Shared implementation for config set human/boss."""
    from delegate.config import add_member

    add_member(hc_home, name)
    click.echo(f"Human member set to: {name}")


@config_set.command("human")
@click.argument("name")
@click.pass_context
def config_set_human(ctx: click.Context, name: str) -> None:
    """Set the human member name."""
    _set_human_name(_get_home(ctx), name)


@config_set.command("boss")
@click.argument("name")
@click.pass_context
def config_set_boss(ctx: click.Context, name: str) -> None:
    """(Deprecated) Alias for 'config set human'."""
    _set_human_name(_get_home(ctx), name)


@config_set.command("source-repo")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_context
def config_set_source_repo(ctx: click.Context, path: Path) -> None:
    """Set the path to the delegate source repository (for self-update)."""
    from delegate.config import set_source_repo

    hc_home = _get_home(ctx)
    set_source_repo(hc_home, path.resolve())
    click.echo(f"Source repo set to: {path.resolve()}")


@config.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show the current configuration."""
    from delegate.config import get_default_human, get_source_repo, get_human_members

    hc_home = _get_home(ctx)
    human = get_default_human(hc_home)
    source_repo = get_source_repo(hc_home) or "(not set)"

    # Members
    members = get_human_members(hc_home)
    member_names = ", ".join(m["name"] for m in members) if members else "(none)"
    click.echo(f"Members:     {member_names}")
    click.echo(f"Default:     {human}")
    click.echo(f"Source repo: {source_repo}")

    # List teams and their repos
    td = _teams_dir(hc_home)
    if td.is_dir():
        teams = sorted(d.name for d in td.iterdir() if d.is_dir())
        if teams:
            from delegate.config import get_repos
            click.echo(f"Teams:       {len(teams)}")
            for t in teams:
                repos = get_repos(hc_home, t)
                click.echo(f"  {t}: {len(repos)} repo(s)")
                for rn, meta in repos.items():
                    click.echo(f"    - {rn}: {meta.get('source', '?')}")


# ──────────────────────────────────────────────────────────────
# delegate repo add / list
# ──────────────────────────────────────────────────────────────

@main.group()
def repo() -> None:
    """Manage registered repositories."""
    pass


@repo.command("add")
@click.argument("team_name")
@click.argument("path_or_url")
@click.option("--name", "repo_name", default=None, help="Name for the repo (default: derived from path/URL).")
@click.option(
    "--approval",
    type=click.Choice(["auto", "manual"], case_sensitive=False),
    default=None,
    help="Merge approval mode: 'auto' (merge when QA approves) or 'manual' (require human approval). Default: manual.",
)
@click.option(
    "--test-cmd",
    default=None,
    help="Shell command to run tests (e.g. '/path/to/.venv/bin/python -m pytest -x -q').",
)
@click.pass_context
def repo_add(ctx: click.Context, team_name: str, path_or_url: str, repo_name: str | None, approval: str | None, test_cmd: str | None) -> None:
    """Register a repository for a team.

    TEAM_NAME is the team this repo belongs to.
    PATH_OR_URL is a local path or remote URL.
    """
    from delegate.repo import register_repo

    hc_home = _get_home(ctx)
    name = register_repo(hc_home, team_name, path_or_url, name=repo_name, approval=approval, test_cmd=test_cmd)
    click.echo(f"Registered repo '{name}' for team '{team_name}'")


@repo.command("list")
@click.argument("team_name")
@click.pass_context
def repo_list(ctx: click.Context, team_name: str) -> None:
    """List registered repositories for a team."""
    from delegate.config import get_repos

    hc_home = _get_home(ctx)
    repos = get_repos(hc_home, team_name)
    if not repos:
        click.echo(f"No repositories registered for team '{team_name}'.")
        return

    click.echo(f"Repos for team '{team_name}':")
    for name, meta in repos.items():
        click.echo(f"  - {name}: {meta.get('source', '?')}")


# ──────────────────────────────────────────────────────────────
# delegate self-update
# ──────────────────────────────────────────────────────────────

@main.command("self-update")
@click.pass_context
def self_update(ctx: click.Context) -> None:
    """Update delegate from the source repository.

    Runs 'git pull' in the source repo and reinstalls the package.
    """
    from delegate.config import get_source_repo

    hc_home = _get_home(ctx)
    source_repo = get_source_repo(hc_home)
    if source_repo is None:
        click.echo("Error: No source repo configured.")
        click.echo("Set one with: delegate config set source-repo /path/to/delegate")
        raise SystemExit(1)

    if not source_repo.is_dir():
        click.echo(f"Error: Source repo not found at {source_repo}")
        raise SystemExit(1)

    # Step 1: git pull
    click.echo(f"Updating source repo at {source_repo}...")
    result = subprocess.run(
        ["git", "pull", "--rebase"],
        cwd=str(source_repo),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        click.echo(f"Git pull failed:\n{result.stderr}")
        raise SystemExit(1)
    click.echo(result.stdout.strip())

    # Step 2: reinstall
    click.echo("Reinstalling delegate...")
    install_cmd = [sys.executable, "-m", "pip", "install", "-e", str(source_repo)]

    # Prefer uv if available
    import shutil
    if shutil.which("uv"):
        install_cmd = ["uv", "pip", "install", "-e", str(source_repo)]

    result = subprocess.run(install_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        click.echo(f"Install failed:\n{result.stderr}")
        raise SystemExit(1)

    click.echo("Delegate updated successfully. ✓")


# ──────────────────────────────────────────────────────────────
# delegate workflow add / list / show / update-actions
# ──────────────────────────────────────────────────────────────

@main.group("workflow")
def workflow_group() -> None:
    """Manage task workflows."""
    pass


@workflow_group.command("add")
@click.argument("team_name")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def workflow_add(ctx: click.Context, team_name: str, path: Path) -> None:
    """Register a workflow for a team.

    TEAM_NAME is the team this workflow belongs to.
    PATH is the Python workflow definition file.

    The file must use the @workflow decorator to define at least one
    workflow with a name and version.  The version must be higher than
    any existing version for that workflow name.

    Example:
        delegate workflow add myteam ./pipelines/my-workflow.py
    """
    from delegate.workflow import register_workflow
    from delegate.fmt import success

    hc_home = _get_home(ctx)
    try:
        wf = register_workflow(hc_home, team_name, path)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))

    success(f"Registered workflow '{wf.name}' v{wf.version} for team '{team_name}'")
    click.echo(wf.format_graph())


@workflow_group.command("list")
@click.argument("team_name")
@click.pass_context
def workflow_list(ctx: click.Context, team_name: str) -> None:
    """List workflows registered for a team."""
    from delegate.workflow import list_workflows

    hc_home = _get_home(ctx)
    workflows = list_workflows(hc_home, team_name)

    if not workflows:
        click.echo(f"No workflows registered for team '{team_name}'.")
        return

    click.echo(f"Workflows for team '{team_name}':")
    for wf in workflows:
        versions_str = ", ".join(f"v{v}" for v in wf["all_versions"])
        stage_count = len(wf["stages"])
        click.echo(
            f"  {click.style(wf['name'], bold=True)} "
            f"(latest: v{wf['version']}, {stage_count} stages) "
            f"[{versions_str}]"
        )


@workflow_group.command("show")
@click.argument("team_name")
@click.argument("name")
@click.option("--version", "version", type=int, default=None, help="Show a specific version (default: latest).")
@click.pass_context
def workflow_show(ctx: click.Context, team_name: str, name: str, version: int | None) -> None:
    """Show the details and graph of a workflow."""
    from delegate.workflow import load_workflow, get_latest_version

    hc_home = _get_home(ctx)

    if version is None:
        version = get_latest_version(hc_home, team_name, name)
        if version is None:
            raise click.ClickException(f"No workflow '{name}' found for team '{team_name}'.")

    try:
        wf = load_workflow(hc_home, team_name, name, version)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))

    click.echo(wf.format_graph())
    click.echo()
    click.echo(f"Source: {wf.source_path}")


@workflow_group.command("update-actions")
@click.argument("team_name")
@click.argument("name")
@click.argument("actions_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.pass_context
def workflow_update_actions(ctx: click.Context, team_name: str, name: str, actions_path: Path) -> None:
    """Update actions for an existing workflow (no version bump).

    TEAM_NAME is the team.
    NAME is the workflow name.
    ACTIONS_PATH is the directory containing action scripts.

    This replaces the workflow's actions directory without changing
    the stage graph or requiring a version bump.
    """
    from delegate.workflow import update_actions
    from delegate.fmt import success

    hc_home = _get_home(ctx)
    try:
        update_actions(hc_home, team_name, name, actions_path)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))

    success(f"Updated actions for workflow '{name}' (team '{team_name}')")


@workflow_group.command("init")
@click.argument("team_name")
@click.pass_context
def workflow_init(ctx: click.Context, team_name: str) -> None:
    """Register the built-in 'default' workflow for a team.

    This copies the default workflow shipped with Delegate into the
    team's workflows directory.  Safe to re-run.
    """
    from delegate.workflow import register_workflow, get_latest_version
    from delegate.fmt import success, info

    hc_home = _get_home(ctx)

    # Check if already registered
    current = get_latest_version(hc_home, team_name, "default")
    if current is not None:
        info(f"Workflow 'default' v{current} already registered for team '{team_name}'")
        return

    # Find the built-in default.py
    builtin = Path(__file__).parent / "workflows" / "default.py"
    if not builtin.is_file():
        raise click.ClickException(f"Built-in default workflow not found at {builtin}")

    try:
        wf = register_workflow(hc_home, team_name, builtin)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))

    success(f"Registered built-in workflow '{wf.name}' v{wf.version} for team '{team_name}'")


# ---------------------------------------------------------------------------
# delegate network …
# ---------------------------------------------------------------------------

@main.group()
def network() -> None:
    """Manage the global network allowlist."""
    pass


@network.command("show")
@click.pass_context
def network_show(ctx: click.Context) -> None:
    """Show the current network allowlist."""
    from delegate.network import get_allowed_domains, DEFAULT_DOMAINS

    hc_home = _get_home(ctx)
    domains = get_allowed_domains(hc_home)

    is_default = set(domains) == set(DEFAULT_DOMAINS)
    header = "Network allowlist (default):" if is_default else "Network allowlist:"
    click.echo(header)
    for d in sorted(domains):
        click.echo(f"  - {d}")


@network.command("allow")
@click.argument("domain")
@click.pass_context
def network_allow(ctx: click.Context, domain: str) -> None:
    """Add a domain to the allowlist.

    DOMAIN can be an exact domain (api.github.com), a wildcard
    (*.openai.com), or '*' to allow all.
    """
    from delegate.network import allow_domain
    from delegate.fmt import success

    hc_home = _get_home(ctx)
    try:
        updated = allow_domain(hc_home, domain)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    success(f"Added '{domain}' to network allowlist")
    for d in sorted(updated):
        click.echo(f"  - {d}")


@network.command("disallow")
@click.argument("domain")
@click.pass_context
def network_disallow(ctx: click.Context, domain: str) -> None:
    """Remove a domain from the allowlist."""
    from delegate.network import disallow_domain
    from delegate.fmt import success

    hc_home = _get_home(ctx)
    try:
        updated = disallow_domain(hc_home, domain)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    success(f"Removed '{domain}' from network allowlist")
    for d in sorted(updated):
        click.echo(f"  - {d}")


@network.command("reset")
@click.pass_context
def network_reset(ctx: click.Context) -> None:
    """Reset the allowlist to the default wildcard (allow all)."""
    from delegate.network import reset_config
    from delegate.fmt import success

    hc_home = _get_home(ctx)
    reset_config(hc_home)
    success("Network allowlist reset to * (unrestricted)")


# ──────────────────────────────────────────────────────────────
# delegate nuke
# ──────────────────────────────────────────────────────────────

@main.command()
@click.pass_context
def nuke(ctx: click.Context) -> None:
    """Destroy all Delegate state by deleting ~/.delegate.

    WARNING: This permanently deletes ALL Delegate data including teams,
    agents, tasks, history, database, and configuration. This cannot be undone.

    Requires interactive confirmation by typing "delete everything".
    """
    import shutil
    from delegate.fmt import warn, success

    hc_home = _get_home(ctx)

    # Show warning and prompt for confirmation
    click.echo()
    warn("This will permanently delete ALL Delegate data including:")
    click.echo("  - All teams and agent data")
    click.echo("  - All tasks and history")
    click.echo("  - All configuration")
    click.echo("  - Database")
    click.echo()
    click.echo(f"Directory: {hc_home}")
    click.echo()

    confirmation = click.prompt('Type "delete everything" to confirm', type=str)

    if confirmation != "delete everything":
        click.echo("Aborted. Nothing was deleted.")
        return

    # Delete the entire delegate home directory
    click.echo(f"Nuking {hc_home}...")
    if hc_home.exists():
        shutil.rmtree(hc_home)
        success("Done. All Delegate data has been removed.")
    else:
        click.echo(f"Directory {hc_home} does not exist. Nothing to delete.")


if __name__ == "__main__":
    main()
