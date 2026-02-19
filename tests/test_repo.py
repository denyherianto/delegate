"""Tests for delegate/repo.py — repo registration via symlinks and worktrees."""

import json
import subprocess
from pathlib import Path

import pytest

from delegate.bootstrap import bootstrap
from delegate.config import set_boss, add_repo
from delegate.repo import (
    register_repo,
    update_repo_path,
    list_repos,
    get_repo_path,
    create_agent_worktree,
    remove_agent_worktree,
    get_worktree_path,
    generate_env_scripts,
)
from delegate.task import create_task, update_task, get_task


TEAM = "myteam"


@pytest.fixture
def hc_home(tmp_path):
    """Create a fully bootstrapped delegate home directory."""
    hc = tmp_path / "hc_home"
    hc.mkdir()
    set_boss(hc, "nikhil")
    bootstrap(hc, TEAM, manager="edison", agents=["alice", "bob", ("sarah", "qa")])
    return hc


@pytest.fixture
def local_repo(tmp_path):
    """Create a local git repo with a main branch."""
    repo = tmp_path / "myproject"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True)
    (repo / "README.md").write_text("# Project\n")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo), capture_output=True, check=True)
    return repo


class TestRegisterRepo:
    def test_creates_symlink(self, hc_home, local_repo):
        name = register_repo(hc_home, TEAM, str(local_repo))
        link = get_repo_path(hc_home, TEAM, name)
        assert link.is_symlink()
        assert link.resolve() == local_repo.resolve()

    def test_derives_name_from_path(self, hc_home, local_repo):
        name = register_repo(hc_home, TEAM, str(local_repo))
        assert name == local_repo.name

    def test_custom_name(self, hc_home, local_repo):
        name = register_repo(hc_home, TEAM, str(local_repo), name="custom")
        assert name == "custom"
        link = get_repo_path(hc_home, TEAM, "custom")
        assert link.is_symlink()

    def test_rejects_remote_url(self, hc_home):
        with pytest.raises(ValueError, match="Remote URLs are not supported"):
            register_repo(hc_home, TEAM, "https://github.com/org/repo.git")

    def test_rejects_missing_path(self, hc_home, tmp_path):
        with pytest.raises(FileNotFoundError):
            register_repo(hc_home, TEAM, str(tmp_path / "nonexistent"))

    def test_rejects_no_git_dir(self, hc_home, tmp_path):
        no_git = tmp_path / "not_a_repo"
        no_git.mkdir()
        with pytest.raises(FileNotFoundError, match="No .git"):
            register_repo(hc_home, TEAM, str(no_git))

    def test_registers_in_config(self, hc_home, local_repo):
        register_repo(hc_home, TEAM, str(local_repo))
        repos = list_repos(hc_home, TEAM)
        assert local_repo.name in repos

    def test_idempotent(self, hc_home, local_repo):
        name1 = register_repo(hc_home, TEAM, str(local_repo))
        name2 = register_repo(hc_home, TEAM, str(local_repo))
        assert name1 == name2

    def test_updates_symlink_on_move(self, hc_home, local_repo, tmp_path):
        register_repo(hc_home, TEAM, str(local_repo))
        new_loc = tmp_path / "moved_repo"
        local_repo.rename(new_loc)
        # Re-register with same name pointing to new location
        register_repo(hc_home, TEAM, str(new_loc), name=local_repo.name)
        link = get_repo_path(hc_home, TEAM, local_repo.name)
        assert link.resolve() == new_loc.resolve()


class TestUpdateRepoPath:
    def test_updates_symlink(self, hc_home, local_repo, tmp_path):
        register_repo(hc_home, TEAM, str(local_repo))
        new_loc = tmp_path / "moved"
        new_loc.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=str(new_loc), capture_output=True, check=True)

        update_repo_path(hc_home, TEAM, local_repo.name, str(new_loc))
        link = get_repo_path(hc_home, TEAM, local_repo.name)
        assert link.resolve() == new_loc.resolve()

    def test_raises_for_unknown_repo(self, hc_home, tmp_path):
        with pytest.raises(FileNotFoundError):
            update_repo_path(hc_home, TEAM, "nonexistent", str(tmp_path))


class TestWorktree:
    def test_create_and_get_worktree(self, hc_home, local_repo):
        register_repo(hc_home, TEAM, str(local_repo))
        repo_name = local_repo.name

        wt_path = create_agent_worktree(
            hc_home, TEAM, repo_name, "alice", task_id=1, branch="alice/T0001",
        )
        assert wt_path.is_dir()
        assert (wt_path / "README.md").exists()

        expected = get_worktree_path(hc_home, TEAM, repo_name, "alice", 1)
        assert wt_path == expected

    def test_records_base_sha(self, hc_home, local_repo):
        register_repo(hc_home, TEAM, str(local_repo))
        repo_name = local_repo.name

        # Create a task to receive the base_sha
        task = create_task(hc_home, TEAM, title="Test task", assignee="manager")
        update_task(hc_home, TEAM, task["id"], repo=repo_name)

        create_agent_worktree(
            hc_home, TEAM, repo_name, "alice", task_id=task["id"], branch="alice/T0001",
        )

        updated = get_task(hc_home, TEAM, task["id"])
        assert updated["base_sha"] != {}
        assert isinstance(updated["base_sha"], dict)
        sha = updated["base_sha"][repo_name]
        assert len(sha) == 40  # Full SHA

    def test_remove_worktree(self, hc_home, local_repo):
        register_repo(hc_home, TEAM, str(local_repo))
        repo_name = local_repo.name

        wt_path = create_agent_worktree(
            hc_home, TEAM, repo_name, "alice", task_id=2, branch="alice/T0002",
        )
        assert wt_path.is_dir()

        remove_agent_worktree(hc_home, TEAM, repo_name, "alice", 2)
        assert not wt_path.exists()

    def test_remove_worktree_prunes_when_directory_missing(self, hc_home, local_repo):
        """Verify git worktree prune runs even when worktree directory is already gone."""
        register_repo(hc_home, TEAM, str(local_repo))
        repo_name = local_repo.name
        real_repo = get_repo_path(hc_home, TEAM, repo_name).resolve()

        # Create and then manually delete the worktree directory (not via git)
        wt_path = create_agent_worktree(
            hc_home, TEAM, repo_name, "alice", task_id=5, branch="alice/T0005",
        )
        assert wt_path.is_dir()

        # Manually delete directory to simulate the bug scenario
        import shutil
        shutil.rmtree(wt_path)
        assert not wt_path.exists()

        # Verify git still sees the worktree in metadata
        result = subprocess.run(
            ["git", "worktree", "list"],
            cwd=str(real_repo),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "alice/T0005" in result.stdout

        # Call remove_agent_worktree — should prune even though dir is gone
        remove_agent_worktree(hc_home, TEAM, repo_name, "alice", 5)

        # Verify git metadata is cleaned up
        result = subprocess.run(
            ["git", "worktree", "list"],
            cwd=str(real_repo),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "alice/T0005" not in result.stdout

        # Clean up the branch so we can reuse the name
        subprocess.run(
            ["git", "branch", "-D", "alice/T0005"],
            cwd=str(real_repo),
            capture_output=True,
            check=False,
        )

        # Verify we can now create a new worktree with the same branch name
        wt_path2 = create_agent_worktree(
            hc_home, TEAM, repo_name, "alice", task_id=6, branch="alice/T0005",
        )
        assert wt_path2.is_dir()

    def test_idempotent_create(self, hc_home, local_repo):
        register_repo(hc_home, TEAM, str(local_repo))
        repo_name = local_repo.name

        wt1 = create_agent_worktree(
            hc_home, TEAM, repo_name, "alice", task_id=3, branch="alice/T0003",
        )
        wt2 = create_agent_worktree(
            hc_home, TEAM, repo_name, "alice", task_id=3, branch="alice/T0003",
        )
        assert wt1 == wt2

    def test_backfills_base_sha_on_existing_worktree(self, hc_home, local_repo):
        """When worktree already exists but task has no base_sha, backfill it."""
        register_repo(hc_home, TEAM, str(local_repo))
        repo_name = local_repo.name

        # Create a task
        task = create_task(hc_home, TEAM, title="Backfill test", assignee="manager")
        update_task(hc_home, TEAM, task["id"], repo=repo_name)

        # First call creates the worktree and sets base_sha
        create_agent_worktree(
            hc_home, TEAM, repo_name, "alice", task_id=task["id"], branch="alice/T0001",
        )
        t1 = get_task(hc_home, TEAM, task["id"])
        assert isinstance(t1["base_sha"], dict)
        assert repo_name in t1["base_sha"]

        # Clear base_sha to simulate the bug
        update_task(hc_home, TEAM, task["id"], base_sha={})
        t_cleared = get_task(hc_home, TEAM, task["id"])
        assert t_cleared["base_sha"] == {}

        # Second call should backfill base_sha even though worktree exists
        create_agent_worktree(
            hc_home, TEAM, repo_name, "alice", task_id=task["id"], branch="alice/T0001",
        )
        t2 = get_task(hc_home, TEAM, task["id"])
        assert isinstance(t2["base_sha"], dict)
        assert len(t2["base_sha"][repo_name]) == 40


class TestGenerateEnvScripts:
    """Unit tests for generate_env_scripts() stack detection and script generation."""

    SETUP = ".delegate.setup.sh"
    TEST = ".delegate.test.sh"
    SHEBANG = "#!/usr/bin/env bash"
    SET_E = "set -e"

    def _read(self, d: Path, name: str) -> str:
        return (d / name).read_text()

    def test_python_pyproject_generates_correct_scripts(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        generate_env_scripts(tmp_path)
        setup = self._read(tmp_path, self.SETUP)
        test = self._read(tmp_path, self.TEST)
        # Must have Python section
        assert "# Python" in setup
        assert "pytest" in test
        # uv or python -m venv
        assert (".venv" in setup)

    def test_python_requirements_txt_no_pyproject(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests\n")
        generate_env_scripts(tmp_path)
        setup = self._read(tmp_path, self.SETUP)
        test = self._read(tmp_path, self.TEST)
        assert "requirements.txt" in setup
        assert "pytest" in test

    def test_node_package_json_generates_correct_scripts(self, tmp_path):
        pkg = {"name": "myapp", "scripts": {"test": "jest"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        generate_env_scripts(tmp_path)
        setup = self._read(tmp_path, self.SETUP)
        test = self._read(tmp_path, self.TEST)
        assert "node_modules" in setup
        assert "npm test" in test

    def test_node_no_test_script_uses_echo(self, tmp_path):
        pkg = {"name": "myapp", "scripts": {}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        generate_env_scripts(tmp_path)
        test = self._read(tmp_path, self.TEST)
        assert "No tests configured" in test

    def test_does_not_overwrite_existing_setup_script(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        original = "#!/usr/bin/env bash\n# custom user script\n"
        (tmp_path / self.SETUP).write_text(original)
        written_setup, written_test = generate_env_scripts(tmp_path)
        assert written_setup is False
        assert written_test is False
        # Content unchanged
        assert self._read(tmp_path, self.SETUP) == original
        # Test script not created either
        assert not (tmp_path / self.TEST).exists()

    def test_shebang_and_set_e_in_both_scripts(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        generate_env_scripts(tmp_path)
        for name in (self.SETUP, self.TEST):
            content = self._read(tmp_path, name)
            assert content.startswith(self.SHEBANG), f"{name} missing shebang"
            assert self.SET_E in content, f"{name} missing set -e"

    def test_scripts_are_executable(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        generate_env_scripts(tmp_path)
        import stat
        for name in (self.SETUP, self.TEST):
            mode = (tmp_path / name).stat().st_mode
            assert mode & stat.S_IXUSR, f"{name} not executable"

    def test_no_indicators_generates_empty_scripts_with_comment(self, tmp_path):
        generate_env_scripts(tmp_path)
        for name in (self.SETUP, self.TEST):
            content = self._read(tmp_path, name)
            assert "No stack detected" in content

    def test_multilanguage_root_pyproject_and_frontend_package_json(self, tmp_path):
        """Root pyproject.toml + frontend/package.json → both sections in scripts."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'backend'\n")
        frontend = tmp_path / "frontend"
        frontend.mkdir()
        pkg = {"name": "frontend", "scripts": {"test": "jest"}}
        (frontend / "package.json").write_text(json.dumps(pkg))
        generate_env_scripts(tmp_path)
        setup = self._read(tmp_path, self.SETUP)
        test = self._read(tmp_path, self.TEST)
        # Both stacks present
        assert "# Python" in setup
        assert "# JavaScript" in setup or "# TypeScript" in setup
        # Frontend uses subshell
        assert "(cd frontend" in setup
        assert "(cd frontend" in test
        assert "pytest" in test

    def test_subdir_detection_backend_pyproject(self, tmp_path):
        """backend/pyproject.toml detected and generates (cd backend && ...) section."""
        backend = tmp_path / "backend"
        backend.mkdir()
        (backend / "pyproject.toml").write_text("[project]\nname = 'backend'\n")
        generate_env_scripts(tmp_path)
        setup = self._read(tmp_path, self.SETUP)
        test = self._read(tmp_path, self.TEST)
        assert "(cd backend" in setup
        assert "(cd backend" in test

    def test_typescript_label_when_tsconfig_present(self, tmp_path):
        """package.json + tsconfig.json → TypeScript label in comment."""
        pkg = {"name": "myapp", "scripts": {"test": "jest"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {}}')
        generate_env_scripts(tmp_path)
        setup = self._read(tmp_path, self.SETUP)
        assert "# TypeScript" in setup

    def test_java_maven_pom_xml(self, tmp_path):
        """pom.xml → correct mvn commands."""
        (tmp_path / "pom.xml").write_text("<project/>")
        generate_env_scripts(tmp_path)
        setup = self._read(tmp_path, self.SETUP)
        test = self._read(tmp_path, self.TEST)
        assert "mvn" in setup
        assert "mvn" in test

    def test_csharp_csproj_dotnet_commands(self, tmp_path):
        """*.csproj glob → dotnet commands."""
        (tmp_path / "MyApp.csproj").write_text("<Project/>")
        generate_env_scripts(tmp_path)
        setup = self._read(tmp_path, self.SETUP)
        test = self._read(tmp_path, self.TEST)
        assert "dotnet restore" in setup
        assert "dotnet test" in test

    def test_rust_cargo_toml(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'myapp'\n")
        generate_env_scripts(tmp_path)
        setup = self._read(tmp_path, self.SETUP)
        test = self._read(tmp_path, self.TEST)
        assert "cargo build" in setup
        assert "cargo test" in test

    def test_go_mod(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/myapp\n\ngo 1.21\n")
        generate_env_scripts(tmp_path)
        setup = self._read(tmp_path, self.SETUP)
        test = self._read(tmp_path, self.TEST)
        assert "go mod tidy" in setup
        assert "go test ./..." in test
