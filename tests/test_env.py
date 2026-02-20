"""Tests for delegate.env — deterministic setup.sh / premerge.sh generation."""

import json
import subprocess
from pathlib import Path

import pytest

from delegate.env import (
    _detect_all,
    _detect_at,
    _parse_envrc,
    generate_env_scripts,
    write_env_scripts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """Create a minimal directory with the given files."""
    d = tmp_path / "repo"
    d.mkdir()
    for name, content in (files or {}).items():
        parent = (d / name).parent
        parent.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(content)
    return d


def _init_git_repo(path: Path) -> None:
    """Initialise a bare git repo so write_env_scripts can commit."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=str(path), capture_output=True, check=True,
        env={
            **__import__("os").environ,
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t",
        },
    )


# ---------------------------------------------------------------------------
# Single-directory detection (_detect_at)
# ---------------------------------------------------------------------------

class TestDetectAt:
    """Test _detect_at identifies the correct stack at a single directory."""

    def test_poetry(self, tmp_path):
        repo = _make_repo(tmp_path, {"poetry.lock": "", "pyproject.toml": ""})
        comp = _detect_at(repo)
        assert comp is not None
        assert comp.name == "python-poetry"

    def test_uv_lock_with_dep_groups(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "uv.lock": "",
            "pyproject.toml": "[dependency-groups]\ndev = [\"pytest\"]\n",
        })
        comp = _detect_at(repo)
        assert comp.name == "python-uv-lock"
        assert "uv sync --group dev" in comp.setup_snippet

    def test_uv_lock_with_optional_deps(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "uv.lock": "",
            "pyproject.toml": "[project.optional-dependencies]\ndev = [\"pytest\"]\n",
        })
        comp = _detect_at(repo)
        assert comp.name == "python-uv-lock"
        assert "uv sync --extra dev" in comp.setup_snippet

    def test_uv_lock_plain(self, tmp_path):
        repo = _make_repo(tmp_path, {"uv.lock": "", "pyproject.toml": "[project]\n"})
        comp = _detect_at(repo)
        assert comp.name == "python-uv-lock"
        assert "uv sync --quiet" in comp.setup_snippet
        assert "--group" not in comp.setup_snippet
        assert "--extra" not in comp.setup_snippet

    def test_pyproject_no_lock(self, tmp_path):
        repo = _make_repo(tmp_path, {"pyproject.toml": "[project]\n"})
        comp = _detect_at(repo)
        assert comp.name == "python"

    def test_requirements_txt(self, tmp_path):
        repo = _make_repo(tmp_path, {"requirements.txt": "flask\n"})
        comp = _detect_at(repo)
        assert comp.name == "python"
        assert "requirements.txt" in comp.setup_snippet

    def test_node_pnpm(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "package.json": '{"scripts":{"test":"vitest"}}',
            "pnpm-lock.yaml": "",
        })
        comp = _detect_at(repo)
        assert comp.name == "node"
        assert "pnpm install" in comp.setup_snippet

    def test_node_yarn(self, tmp_path):
        repo = _make_repo(tmp_path, {"package.json": '{}', "yarn.lock": ""})
        comp = _detect_at(repo)
        assert comp.name == "node"
        assert "yarn install" in comp.setup_snippet

    def test_node_npm(self, tmp_path):
        repo = _make_repo(tmp_path, {"package.json": '{}', "package-lock.json": ""})
        comp = _detect_at(repo)
        assert comp.name == "node"
        assert "npm ci" in comp.setup_snippet

    def test_rust(self, tmp_path):
        repo = _make_repo(tmp_path, {"Cargo.toml": ""})
        comp = _detect_at(repo)
        assert comp.name == "rust"
        assert "cargo build" in comp.setup_snippet

    def test_go(self, tmp_path):
        repo = _make_repo(tmp_path, {"go.mod": ""})
        comp = _detect_at(repo)
        assert comp.name == "go"
        assert "go mod tidy" in comp.setup_snippet

    def test_ruby(self, tmp_path):
        repo = _make_repo(tmp_path, {"Gemfile": ""})
        comp = _detect_at(repo)
        assert comp.name == "ruby"
        assert "bundle install" in comp.setup_snippet

    def test_unknown(self, tmp_path):
        repo = _make_repo(tmp_path)
        comp = _detect_at(repo)
        assert comp is None

    def test_poetry_takes_priority_over_uv_lock(self, tmp_path):
        repo = _make_repo(tmp_path, {"poetry.lock": "", "uv.lock": "", "pyproject.toml": ""})
        comp = _detect_at(repo)
        assert comp.name == "python-poetry"

    def test_subdir_path_scoped(self, tmp_path):
        """Subdir detection should scope paths to the subdirectory."""
        repo = _make_repo(tmp_path, {"server/go.mod": ""})
        comp = _detect_at(repo / "server", "server")
        assert comp is not None
        assert comp.rel_path == "server"
        assert "server" in comp.setup_snippet
        assert "server" in comp.test_cmd


# ---------------------------------------------------------------------------
# Multi-directory detection (_detect_all)
# ---------------------------------------------------------------------------

class TestDetectAll:
    """Test scanning root + subdirs for all stacks."""

    def test_single_root_stack(self, tmp_path):
        repo = _make_repo(tmp_path, {"Cargo.toml": ""})
        comps = _detect_all(repo)
        assert len(comps) == 1
        assert comps[0].name == "rust"
        assert comps[0].is_root

    def test_root_plus_subdir(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "pyproject.toml": "[project]\n",
            "frontend/package.json": '{"scripts":{"test":"vitest"}}',
            "frontend/package-lock.json": "",
        })
        comps = _detect_all(repo)
        names = [(c.rel_path, c.name) for c in comps]
        assert (".", "python") in names
        assert ("frontend", "node") in names

    def test_three_stacks(self, tmp_path):
        """Rust backend + Python server + TypeScript infra."""
        repo = _make_repo(tmp_path, {
            "backend/Cargo.toml": "",
            "server/pyproject.toml": "[project]\n",
            "infra/package.json": '{"scripts":{"test":"cdk synth"}}',
            "infra/package-lock.json": "",
        })
        comps = _detect_all(repo)
        names = {c.rel_path: c.name for c in comps}
        assert names == {"backend": "rust", "server": "python", "infra": "node"}

    def test_skips_hidden_and_build_dirs(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "Cargo.toml": "",
            ".git/package.json": "{}",       # hidden
            "node_modules/package.json": "{}", # build artifact
            "dist/package.json": "{}",         # build output
        })
        comps = _detect_all(repo)
        assert len(comps) == 1
        assert comps[0].name == "rust"

    def test_empty_repo_returns_unknown(self, tmp_path):
        repo = _make_repo(tmp_path)
        comps = _detect_all(repo)
        assert len(comps) == 1
        assert comps[0].name == "unknown"

    def test_nix_detected_at_root(self, tmp_path):
        """Nix files at root should be picked up by generate_env_scripts."""
        repo = _make_repo(tmp_path, {"shell.nix": "", "pyproject.toml": "[project]\n"})
        setup, _ = generate_env_scripts(repo)
        assert "nix-shell" in setup

    def test_flake_nix_preferred(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "flake.nix": "", "shell.nix": "", "pyproject.toml": "[project]\n",
        })
        setup, _ = generate_env_scripts(repo)
        assert "nix develop" in setup


# ---------------------------------------------------------------------------
# Script generation
# ---------------------------------------------------------------------------

class TestGenerateScripts:
    """Test that generated scripts have the right structure."""

    def test_header_present(self, tmp_path):
        repo = _make_repo(tmp_path, {"Cargo.toml": ""})
        setup, premerge = generate_env_scripts(repo)
        assert setup.startswith("#!/usr/bin/env bash\n")
        assert premerge.startswith("#!/usr/bin/env bash\n")

    def test_set_e(self, tmp_path):
        repo = _make_repo(tmp_path, {"go.mod": ""})
        setup, premerge = generate_env_scripts(repo)
        assert "set -e" in setup
        assert "set -e" in premerge

    def test_reentrance_guard(self, tmp_path):
        repo = _make_repo(tmp_path, {"Cargo.toml": ""})
        setup, _ = generate_env_scripts(repo)
        assert "_DELEGATE_SETUP_DONE" in setup

    def test_python_venv_isolation(self, tmp_path):
        repo = _make_repo(tmp_path, {"pyproject.toml": "[project]\n"})
        setup, _ = generate_env_scripts(repo)
        assert 'VENV_DIR="$WORKTREE_ROOT/.venv"' in setup

    def test_python_uv_lock_uses_sync(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "uv.lock": "",
            "pyproject.toml": "[dependency-groups]\ndev = [\"pytest\"]\n",
        })
        setup, _ = generate_env_scripts(repo)
        assert "uv sync --group dev" in setup
        assert "uv venv" not in setup

    def test_python_no_lock_has_uv_fallback(self, tmp_path):
        repo = _make_repo(tmp_path, {"pyproject.toml": "[project]\n"})
        setup, _ = generate_env_scripts(repo)
        assert "uv venv" in setup
        assert "python3 -m venv" in setup

    def test_premerge_sources_setup(self, tmp_path):
        repo = _make_repo(tmp_path, {"pyproject.toml": "[project]\n"})
        _, premerge = generate_env_scripts(repo)
        assert 'source "$SCRIPT_DIR/setup.sh"' in premerge

    def test_nix_premerge_is_self_contained(self, tmp_path):
        repo = _make_repo(tmp_path, {"shell.nix": "", "pyproject.toml": "[project]\n"})
        _, premerge = generate_env_scripts(repo)
        assert "setup.sh" not in premerge
        assert "nix-shell" in premerge

    def test_nix_setup_uses_repo_root(self, tmp_path):
        repo = _make_repo(tmp_path, {"shell.nix": "", "Cargo.toml": ""})
        setup, _ = generate_env_scripts(repo)
        assert "REPO_ROOT" in setup
        assert "nix-shell" in setup

    def test_node_pnpm_test_cmd(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "package.json": '{"scripts":{"test":"vitest"}}',
            "pnpm-lock.yaml": "",
        })
        _, premerge = generate_env_scripts(repo)
        assert "npm test" in premerge

    def test_poetry_venv_in_project(self, tmp_path):
        repo = _make_repo(tmp_path, {"poetry.lock": "", "pyproject.toml": ""})
        setup, _ = generate_env_scripts(repo)
        assert "POETRY_VIRTUALENVS_IN_PROJECT=true" in setup

    def test_quiet_flags(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "uv.lock": "",
            "pyproject.toml": "[dependency-groups]\ndev=[\"pytest\"]\n",
        })
        setup, _ = generate_env_scripts(repo)
        assert "--quiet" in setup

    def test_scripts_end_with_newline(self, tmp_path):
        repo = _make_repo(tmp_path, {"Cargo.toml": ""})
        setup, premerge = generate_env_scripts(repo)
        assert setup.endswith("\n")
        assert premerge.endswith("\n")


# ---------------------------------------------------------------------------
# Multi-language composition
# ---------------------------------------------------------------------------

class TestMultiLanguage:
    """Test that multi-language repos get properly composed scripts."""

    def test_python_plus_node_frontend(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "uv.lock": "",
            "pyproject.toml": "[dependency-groups]\ndev = [\"pytest\"]\n",
            "frontend/package.json": '{}',
            "frontend/pnpm-lock.yaml": "",
        })
        setup, premerge = generate_env_scripts(repo)
        # Primary Python
        assert "uv sync --group dev" in setup
        # Secondary Node
        assert "frontend/" in setup
        assert "pnpm install" in setup
        # Premerge has Python tests
        assert "pytest" in premerge

    def test_three_subdirs(self, tmp_path):
        """Rust + Python + Node all as subdirectories (no root stack)."""
        repo = _make_repo(tmp_path, {
            "backend/Cargo.toml": "",
            "server/requirements.txt": "flask\n",
            "infra/package.json": '{"scripts":{"test":"cdk synth"}}',
            "infra/package-lock.json": "",
        })
        setup, premerge = generate_env_scripts(repo)
        assert "cargo build" in setup
        assert "requirements.txt" in setup
        assert "npm ci" in setup
        # Premerge runs all three test suites
        assert "cargo test" in premerge
        assert "pytest" in premerge
        assert "npm test" in premerge

    def test_go_plus_two_node_frontends(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "go.mod": "",
            "frontend/package.json": '{"scripts":{"test":"vitest"}}',
            "frontend/pnpm-lock.yaml": "",
            "client/package.json": '{}',
            "client/yarn.lock": "",
        })
        setup, premerge = generate_env_scripts(repo)
        assert "go mod tidy" in setup
        assert "pnpm install" in setup
        assert "yarn install" in setup

    def test_subdir_python_gets_own_venv(self, tmp_path):
        """A Python subdir should create .venv inside its own directory."""
        repo = _make_repo(tmp_path, {
            "Cargo.toml": "",
            "server/pyproject.toml": "[project]\n",
        })
        setup, _ = generate_env_scripts(repo)
        assert "server/.venv" in setup

    def test_no_duplicate_root_and_subdir(self, tmp_path):
        """If root is Node (no workspaces), a 'frontend' subdir is still detected."""
        repo = _make_repo(tmp_path, {
            "package.json": '{"scripts":{"test":"jest"}}',
            "package-lock.json": "",
            "frontend/package.json": '{}',
            "frontend/pnpm-lock.yaml": "",
        })
        comps = _detect_all(repo)
        paths = [c.rel_path for c in comps]
        assert "." in paths
        assert "frontend" in paths


class TestWorkspaceDedup:
    """Test that workspace patterns suppress redundant subdir detection."""

    def test_cargo_workspace_skips_members(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "Cargo.toml": '[workspace]\nmembers = ["backend", "cli"]\n',
            "backend/Cargo.toml": '[package]\nname = "backend"\n',
            "cli/Cargo.toml": '[package]\nname = "cli"\n',
        })
        comps = _detect_all(repo)
        assert len(comps) == 1
        assert comps[0].is_root and comps[0].name == "rust"

    def test_cargo_no_workspace_keeps_subdirs(self, tmp_path):
        """Without [workspace], subdirs with Cargo.toml ARE separate stacks."""
        repo = _make_repo(tmp_path, {
            "backend/Cargo.toml": '[package]\nname = "backend"\n',
            "cli/Cargo.toml": '[package]\nname = "cli"\n',
        })
        comps = _detect_all(repo)
        names = {c.rel_path for c in comps}
        assert "backend" in names
        assert "cli" in names

    def test_npm_workspaces_skips_packages(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "package.json": '{"workspaces":["packages/*"],"scripts":{"test":"jest"}}',
            "package-lock.json": "",
            "packages/ui/package.json": '{}',
            "packages/api/package.json": '{}',
        })
        comps = _detect_all(repo)
        # Root node detected, but packages/ui and packages/api are NOT
        # (they're inside packages/ which is not a direct child, so they
        #  wouldn't be scanned anyway — but direct children would be skipped)
        root_comps = [c for c in comps if c.is_root]
        assert len(root_comps) == 1
        assert root_comps[0].name == "node"

    def test_npm_workspaces_skips_direct_child(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "package.json": '{"workspaces":["frontend"],"scripts":{"test":"jest"}}',
            "package-lock.json": "",
            "frontend/package.json": '{}',
        })
        comps = _detect_all(repo)
        assert len(comps) == 1
        assert comps[0].name == "node" and comps[0].is_root

    def test_npm_no_workspaces_keeps_subdir(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "package.json": '{"scripts":{"test":"jest"}}',
            "package-lock.json": "",
            "frontend/package.json": '{}',
            "frontend/pnpm-lock.yaml": "",
        })
        comps = _detect_all(repo)
        paths = {c.rel_path for c in comps}
        assert "." in paths
        assert "frontend" in paths

    def test_go_work_skips_modules(self, tmp_path):
        repo = _make_repo(tmp_path, {
            "go.mod": "",
            "go.work": 'use (\n\t.\n\t./svc\n)\n',
            "svc/go.mod": "",
        })
        comps = _detect_all(repo)
        assert len(comps) == 1
        assert comps[0].name == "go" and comps[0].is_root

    def test_workspace_dedup_still_allows_different_stacks(self, tmp_path):
        """Cargo workspace should only suppress Rust subdirs, not Node ones."""
        repo = _make_repo(tmp_path, {
            "Cargo.toml": '[workspace]\nmembers = ["backend"]\n',
            "backend/Cargo.toml": '[package]\nname = "backend"\n',
            "frontend/package.json": '{}',
            "frontend/package-lock.json": "",
        })
        comps = _detect_all(repo)
        names = {(c.rel_path, c.name) for c in comps}
        assert (".", "rust") in names
        assert ("frontend", "node") in names
        assert ("backend", "rust") not in names  # suppressed by workspace


# ---------------------------------------------------------------------------
# .envrc detection
# ---------------------------------------------------------------------------

class TestEnvrc:
    """Test .envrc parsing and fallback detection."""

    def test_parse_use_nix(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".envrc").write_text("use nix\n")
        assert "nix" in _parse_envrc(repo)

    def test_parse_use_flake(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".envrc").write_text("use flake\n")
        hints = _parse_envrc(repo)
        assert "nix" in hints
        assert "flake" in hints

    def test_parse_layout_python(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".envrc").write_text("layout python3\n")
        assert "python" in _parse_envrc(repo)

    def test_parse_layout_poetry(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".envrc").write_text("layout poetry\n")
        assert "poetry" in _parse_envrc(repo)

    def test_parse_layout_node(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".envrc").write_text("layout node\n")
        assert "node" in _parse_envrc(repo)

    def test_parse_layout_ruby(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".envrc").write_text("layout ruby\n")
        assert "ruby" in _parse_envrc(repo)

    def test_parse_multiple_hints(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".envrc").write_text("use nix\nlayout python3\n")
        hints = _parse_envrc(repo)
        assert "nix" in hints
        assert "python" in hints

    def test_comments_ignored(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".envrc").write_text("# use nix\nlayout python3\n")
        hints = _parse_envrc(repo)
        assert "nix" not in hints
        assert "python" in hints

    def test_no_envrc_returns_empty(self, tmp_path):
        repo = _make_repo(tmp_path)
        assert _parse_envrc(repo) == set()

    def test_envrc_fallback_detects_python(self, tmp_path):
        """Directory with only .envrc (no pyproject/requirements) → Python."""
        repo = _make_repo(tmp_path)
        (repo / ".envrc").write_text("layout python3\n")
        comp = _detect_at(repo)
        assert comp is not None
        assert comp.name == "python"

    def test_envrc_fallback_detects_poetry(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".envrc").write_text("layout poetry\n")
        comp = _detect_at(repo)
        assert comp is not None
        assert comp.name == "python-poetry"

    def test_envrc_fallback_detects_node(self, tmp_path):
        repo = _make_repo(tmp_path)
        (repo / ".envrc").write_text("layout node\n")
        comp = _detect_at(repo)
        assert comp is not None
        assert comp.name == "node"

    def test_manifest_takes_priority_over_envrc(self, tmp_path):
        """If Cargo.toml exists, .envrc layout python doesn't override it."""
        repo = _make_repo(tmp_path, {"Cargo.toml": ""})
        (repo / ".envrc").write_text("layout python3\n")
        comp = _detect_at(repo)
        assert comp.name == "rust"

    def test_envrc_nix_triggers_nix_wrapper(self, tmp_path):
        """use nix in .envrc (without shell.nix file) → nix-shell in setup."""
        repo = _make_repo(tmp_path, {"pyproject.toml": "[project]\n"})
        (repo / ".envrc").write_text("use nix\n")
        setup, _ = generate_env_scripts(repo)
        assert "nix-shell" in setup

    def test_envrc_flake_triggers_nix_develop(self, tmp_path):
        """use flake in .envrc → nix develop in setup."""
        repo = _make_repo(tmp_path, {"pyproject.toml": "[project]\n"})
        (repo / ".envrc").write_text("use flake\n")
        setup, _ = generate_env_scripts(repo)
        assert "nix develop" in setup


# ---------------------------------------------------------------------------
# write_env_scripts
# ---------------------------------------------------------------------------

class TestWriteEnvScripts:
    """Test writing scripts to disk."""

    def test_creates_delegate_dir(self, tmp_path):
        repo = _make_repo(tmp_path, {"go.mod": ""})
        _init_git_repo(repo)
        assert write_env_scripts(repo) is True
        assert (repo / ".delegate" / "setup.sh").is_file()
        assert (repo / ".delegate" / "premerge.sh").is_file()

    def test_executable_permissions(self, tmp_path):
        repo = _make_repo(tmp_path, {"go.mod": ""})
        _init_git_repo(repo)
        write_env_scripts(repo)
        import stat
        mode = (repo / ".delegate" / "setup.sh").stat().st_mode
        assert mode & stat.S_IXUSR

    def test_skips_if_exists(self, tmp_path):
        repo = _make_repo(tmp_path, {"go.mod": ""})
        _init_git_repo(repo)
        (repo / ".delegate").mkdir()
        (repo / ".delegate" / "setup.sh").write_text("# custom\n")
        assert write_env_scripts(repo) is False

    def test_no_commit_flag(self, tmp_path):
        repo = _make_repo(tmp_path, {"go.mod": ""})
        write_env_scripts(repo, commit=False)
        assert (repo / ".delegate" / "setup.sh").is_file()

    def test_git_commit_created(self, tmp_path):
        repo = _make_repo(tmp_path, {"go.mod": ""})
        _init_git_repo(repo)
        write_env_scripts(repo, commit=True)
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=str(repo), capture_output=True, text=True,
        )
        assert "delegate env scripts" in log.stdout
