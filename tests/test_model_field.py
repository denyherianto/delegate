"""Tests for the model field replacement (replaces seniority).

Covers:
- _default_model() in bootstrap.py
- add_agent() with model param
- bootstrap() with models dict
- Backward compat: old state.yaml with seniority field
- CLI --model option for agent add
- CLI --model option for team create
- Web API AddAgentRequest with model field
- Prompt builds identity with model: not seniority:
"""

from __future__ import annotations

import pytest
import yaml
from click.testing import CliRunner
from fastapi.testclient import TestClient

from delegate.bootstrap import bootstrap, add_agent, _default_model
from delegate.cli import main
from delegate.config import add_member
from delegate.paths import agent_dir
from delegate.web import create_app

TEAM = "testteam"


@pytest.fixture
def hc(tmp_path):
    hc_home = tmp_path / "hc"
    hc_home.mkdir()
    add_member(hc_home, "nikhil")
    return hc_home


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# _default_model
# ---------------------------------------------------------------------------

class TestDefaultModel:
    def test_manager_gets_opus(self):
        assert _default_model("manager") == "opus"

    def test_engineer_gets_sonnet(self):
        assert _default_model("engineer") == "sonnet"

    def test_worker_gets_sonnet(self):
        assert _default_model("worker") == "sonnet"

    def test_designer_gets_sonnet(self):
        assert _default_model("designer") == "sonnet"


# ---------------------------------------------------------------------------
# add_agent with model param
# ---------------------------------------------------------------------------

class TestAddAgentModel:
    def test_add_agent_default_model_engineer(self, hc):
        """Engineer defaults to sonnet."""
        bootstrap(hc, TEAM, manager="mgr", agents=[])
        add_agent(hc, TEAM, agent_name="alice", role="engineer")
        state = yaml.safe_load((agent_dir(hc, TEAM, "alice") / "state.yaml").read_text())
        assert state["model"] == "sonnet"
        assert "seniority" not in state

    def test_add_agent_explicit_opus(self, hc):
        """Explicit model=opus stored in state.yaml."""
        bootstrap(hc, TEAM, manager="mgr", agents=[])
        add_agent(hc, TEAM, agent_name="alice", role="engineer", model="opus")
        state = yaml.safe_load((agent_dir(hc, TEAM, "alice") / "state.yaml").read_text())
        assert state["model"] == "opus"

    def test_add_agent_explicit_sonnet(self, hc):
        """Explicit model=sonnet stored in state.yaml."""
        bootstrap(hc, TEAM, manager="mgr", agents=[])
        add_agent(hc, TEAM, agent_name="bob", role="engineer", model="sonnet")
        state = yaml.safe_load((agent_dir(hc, TEAM, "bob") / "state.yaml").read_text())
        assert state["model"] == "sonnet"

    def test_add_agent_invalid_model_raises(self, hc):
        """Invalid model value raises ValueError."""
        bootstrap(hc, TEAM, manager="mgr", agents=[])
        with pytest.raises(ValueError, match="Invalid model"):
            add_agent(hc, TEAM, agent_name="eve", role="engineer", model="gpt4")

    def test_bootstrap_manager_defaults_to_opus(self, hc):
        """Manager agent state.yaml gets model: opus by default."""
        bootstrap(hc, TEAM, manager="mgr", agents=[])
        state = yaml.safe_load((agent_dir(hc, TEAM, "mgr") / "state.yaml").read_text())
        assert state["model"] == "opus"
        assert "seniority" not in state


# ---------------------------------------------------------------------------
# bootstrap() with models dict
# ---------------------------------------------------------------------------

class TestBootstrapModels:
    def test_wildcard_model_applies_to_all(self, hc):
        """models={'*': 'opus'} sets all non-manager agents to opus."""
        bootstrap(hc, TEAM, manager="mgr", agents=["alice", "bob"],
                  models={"*": "opus"})
        for name in ["alice", "bob"]:
            state = yaml.safe_load((agent_dir(hc, TEAM, name) / "state.yaml").read_text())
            assert state["model"] == "opus", f"{name} should be opus"

    def test_per_agent_model_overrides_wildcard(self, hc):
        """Per-agent entry overrides wildcard."""
        bootstrap(hc, TEAM, manager="mgr", agents=["alice", "bob"],
                  models={"*": "opus", "alice": "sonnet"})
        alice_state = yaml.safe_load((agent_dir(hc, TEAM, "alice") / "state.yaml").read_text())
        bob_state = yaml.safe_load((agent_dir(hc, TEAM, "bob") / "state.yaml").read_text())
        assert alice_state["model"] == "sonnet"
        assert bob_state["model"] == "opus"

    def test_no_models_dict_uses_role_defaults(self, hc):
        """Without models dict, defaults apply (manager=opus, engineer=sonnet)."""
        bootstrap(hc, TEAM, manager="mgr", agents=["alice"])
        mgr_state = yaml.safe_load((agent_dir(hc, TEAM, "mgr") / "state.yaml").read_text())
        alice_state = yaml.safe_load((agent_dir(hc, TEAM, "alice") / "state.yaml").read_text())
        assert mgr_state["model"] == "opus"
        assert alice_state["model"] == "sonnet"


# ---------------------------------------------------------------------------
# Backward compatibility: old state.yaml with seniority field
# ---------------------------------------------------------------------------

class TestBackwardCompatSeniority:
    def test_seniority_senior_maps_to_opus_in_prompt(self, hc):
        """Old state.yaml with seniority: senior resolves to opus in Prompt."""
        from delegate.prompt import Prompt
        bootstrap(hc, TEAM, manager="mgr", agents=["alice"])
        # Overwrite alice's state.yaml with legacy seniority field
        state_path = agent_dir(hc, TEAM, "alice") / "state.yaml"
        state_path.write_text(yaml.dump({"role": "engineer", "seniority": "senior", "pid": None, "token_budget": None}))
        p = Prompt(hc, TEAM, "alice")
        assert p._model == "opus"

    def test_seniority_junior_maps_to_sonnet_in_prompt(self, hc):
        """Old state.yaml with seniority: junior resolves to sonnet in Prompt."""
        from delegate.prompt import Prompt
        bootstrap(hc, TEAM, manager="mgr", agents=["alice"])
        state_path = agent_dir(hc, TEAM, "alice") / "state.yaml"
        state_path.write_text(yaml.dump({"role": "engineer", "seniority": "junior", "pid": None, "token_budget": None}))
        p = Prompt(hc, TEAM, "alice")
        assert p._model == "sonnet"

    def test_model_field_takes_precedence_over_seniority(self, hc):
        """If state.yaml has both model and seniority, model wins."""
        from delegate.prompt import Prompt
        bootstrap(hc, TEAM, manager="mgr", agents=["alice"])
        state_path = agent_dir(hc, TEAM, "alice") / "state.yaml"
        # model=sonnet should win over seniority=senior
        state_path.write_text(yaml.dump({"role": "engineer", "model": "sonnet", "seniority": "senior", "pid": None, "token_budget": None}))
        p = Prompt(hc, TEAM, "alice")
        assert p._model == "sonnet"

    def test_preamble_shows_model_not_seniority(self, hc):
        """Preamble identity line shows model: not seniority:."""
        from delegate.prompt import Prompt
        bootstrap(hc, TEAM, manager="mgr", agents=["alice"])
        preamble = Prompt(hc, TEAM, "alice").build_preamble()
        assert "model: sonnet" in preamble
        assert "seniority:" not in preamble


# ---------------------------------------------------------------------------
# CLI: agent add --model
# ---------------------------------------------------------------------------

class TestCliAgentAddModel:
    def test_agent_add_with_opus_model(self, hc, runner):
        """delegate agent add team alice --model opus stores model: opus."""
        bootstrap(hc, TEAM, manager="mgr", agents=[])
        result = runner.invoke(
            main,
            ["--home", str(hc), "agent", "add", TEAM, "alice", "--model", "opus"],
        )
        assert result.exit_code == 0, result.output
        assert "model: opus" in result.output
        state = yaml.safe_load((agent_dir(hc, TEAM, "alice") / "state.yaml").read_text())
        assert state["model"] == "opus"

    def test_agent_add_with_sonnet_model(self, hc, runner):
        """delegate agent add team bob --model sonnet stores model: sonnet."""
        bootstrap(hc, TEAM, manager="mgr", agents=[])
        result = runner.invoke(
            main,
            ["--home", str(hc), "agent", "add", TEAM, "bob", "--model", "sonnet"],
        )
        assert result.exit_code == 0, result.output
        assert "model: sonnet" in result.output
        state = yaml.safe_load((agent_dir(hc, TEAM, "bob") / "state.yaml").read_text())
        assert state["model"] == "sonnet"

    def test_agent_add_invalid_model_rejected(self, hc, runner):
        """Invalid --model value is rejected by click.Choice."""
        bootstrap(hc, TEAM, manager="mgr", agents=[])
        result = runner.invoke(
            main,
            ["--home", str(hc), "agent", "add", TEAM, "charlie", "--model", "gpt4"],
        )
        assert result.exit_code != 0

    def test_agent_add_no_seniority_option(self, hc, runner):
        """--seniority option is no longer accepted."""
        bootstrap(hc, TEAM, manager="mgr", agents=[])
        result = runner.invoke(
            main,
            ["--home", str(hc), "agent", "add", TEAM, "dave", "--seniority", "junior"],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# CLI: team create --model
# ---------------------------------------------------------------------------

class TestCliTeamCreateModel:
    def test_team_create_with_global_opus(self, hc, runner, tmp_path):
        """--model opus sets all agents to opus."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        result = runner.invoke(
            main,
            ["--home", str(hc), "team", "add", "myteam",
             "--agents", "alice,bob",
             "--repo", str(repo_dir),
             "--model", "opus"],
        )
        assert result.exit_code == 0, result.output
        for name in ["alice", "bob"]:
            state = yaml.safe_load((agent_dir(hc, "myteam", name) / "state.yaml").read_text())
            assert state["model"] == "opus", f"{name} should be opus"

    def test_team_create_with_per_agent_models(self, hc, runner, tmp_path):
        """--model alice:opus,bob:sonnet sets per-agent models."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        result = runner.invoke(
            main,
            ["--home", str(hc), "team", "add", "myteam",
             "--agents", "alice,bob",
             "--repo", str(repo_dir),
             "--model", "alice:opus,bob:sonnet"],
        )
        assert result.exit_code == 0, result.output
        alice_state = yaml.safe_load((agent_dir(hc, "myteam", "alice") / "state.yaml").read_text())
        bob_state = yaml.safe_load((agent_dir(hc, "myteam", "bob") / "state.yaml").read_text())
        assert alice_state["model"] == "opus"
        assert bob_state["model"] == "sonnet"

    def test_team_create_invalid_model_rejected(self, hc, runner, tmp_path):
        """--model with invalid value returns error."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        result = runner.invoke(
            main,
            ["--home", str(hc), "team", "add", "myteam",
             "--agents", "alice",
             "--repo", str(repo_dir),
             "--model", "gpt4"],
        )
        assert result.exit_code != 0

    def test_team_create_no_model_uses_defaults(self, hc, runner, tmp_path):
        """Without --model, defaults apply: manager=opus, engineers=sonnet."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        result = runner.invoke(
            main,
            ["--home", str(hc), "team", "add", "myteam",
             "--agents", "alice",
             "--repo", str(repo_dir)],
        )
        assert result.exit_code == 0, result.output
        mgr_state = yaml.safe_load((agent_dir(hc, "myteam", "delegate") / "state.yaml").read_text())
        alice_state = yaml.safe_load((agent_dir(hc, "myteam", "alice") / "state.yaml").read_text())
        assert mgr_state["model"] == "opus"
        assert alice_state["model"] == "sonnet"


# ---------------------------------------------------------------------------
# Web API: AddAgentRequest with model field
# ---------------------------------------------------------------------------

class TestWebApiModel:
    @pytest.fixture
    def client(self, tmp_team):
        app = create_app(hc_home=tmp_team)
        return TestClient(app)

    def test_add_agent_with_model_opus(self, client, tmp_team):
        """POST /teams/{team}/agents/add with model=opus stores model: opus."""
        from tests.conftest import SAMPLE_TEAM_NAME
        resp = client.post(
            f"/teams/{SAMPLE_TEAM_NAME}/agents/add",
            json={"name": "zara", "role": "engineer", "model": "opus"},
        )
        assert resp.status_code == 200
        assert "model: opus" in resp.json()["message"]
        state = yaml.safe_load((agent_dir(tmp_team, SAMPLE_TEAM_NAME, "zara") / "state.yaml").read_text())
        assert state["model"] == "opus"

    def test_add_agent_without_model_defaults_to_sonnet(self, client, tmp_team):
        """POST /teams/{team}/agents/add without model defaults to sonnet for engineer."""
        from tests.conftest import SAMPLE_TEAM_NAME
        resp = client.post(
            f"/teams/{SAMPLE_TEAM_NAME}/agents/add",
            json={"name": "yuki", "role": "engineer"},
        )
        assert resp.status_code == 200
        assert "model: sonnet" in resp.json()["message"]

    def test_add_agent_no_seniority_field_in_response(self, client, tmp_team):
        """Response message says 'model:' not 'seniority:'."""
        from tests.conftest import SAMPLE_TEAM_NAME
        resp = client.post(
            f"/teams/{SAMPLE_TEAM_NAME}/agents/add",
            json={"name": "wren"},
        )
        assert resp.status_code == 200
        assert "seniority" not in resp.json()["message"]
        assert "model:" in resp.json()["message"]
