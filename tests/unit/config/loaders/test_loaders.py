"""Tests for config.loaders.loaders — load, load_config, normalize."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from strands_compose.config.loaders import load, load_config
from strands_compose.config.loaders.loaders import normalize
from strands_compose.config.resolvers.config import ResolvedConfig
from strands_compose.config.schema import (
    DelegateOrchestrationDef,
    GraphOrchestrationDef,
    SwarmOrchestrationDef,
)
from strands_compose.exceptions import ConfigurationError

from .conftest import (
    _agent_yaml,
    _agents_yaml,
    _delegate_yaml,
    _minimal_yaml,
    _swarm_yaml,
)

# ── load() pipeline ──────────────────────────────────────────────────────


class TestLoad:
    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    @patch("strands_compose.config.loaders.loaders.resolve_infra")
    def test_load_pipeline(
        self, mock_resolve_infra, mock_resolve_agents, mock_resolve_orch, simple_config_yaml
    ):
        """load() resolves infra, creates agents, wires orchestration."""
        mock_infra = MagicMock()
        mock_resolve_infra.return_value = mock_infra
        mock_agent = MagicMock()
        mock_resolve_agents.return_value = {"assistant": mock_agent}
        mock_resolve_orch.return_value = {}

        result = load(simple_config_yaml)

        mock_resolve_infra.assert_called_once()
        mock_infra.mcp_lifecycle.start.assert_called_once()
        mock_resolve_agents.assert_called_once()
        mock_resolve_orch.assert_called_once()

        assert isinstance(result, ResolvedConfig)
        assert result.agents == {"assistant": mock_agent}
        assert result.orchestrators == {}
        assert result.entry is mock_agent
        assert result.mcp_lifecycle is mock_infra.mcp_lifecycle


# ── normalize() ──────────────────────────────────────────────────────────


class TestNormalize:
    def test_version_one_passes_through_unchanged(self):
        result = normalize({"version": "1", "agents": {}, "entry": "a"})
        assert result["version"] == "1"
        assert result["agents"] == {}

    def test_missing_version_defaults_to_one(self):
        assert normalize({"agents": {}, "entry": "a"})["version"] == "1"

    def test_unknown_version_raises_value_error(self):
        with pytest.raises(ValueError, match="schema version '99'"):
            normalize({"version": "99", "agents": {}, "entry": "a"})

    def test_does_not_mutate_input(self):
        raw = {"agents": {}, "entry": "a"}
        original = dict(raw)
        normalize(raw)
        assert raw == original


# ── load_config() ────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_load_simple_config(self, simple_config_yaml):
        config = load_config(simple_config_yaml)
        assert "assistant" in config.agents
        assert config.agents["assistant"].system_prompt == "You are a helpful assistant."

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_invalid_yaml_type(self, write_config):
        with pytest.raises(ValueError, match="YAML mapping"):
            load_config(write_config("just a string\n", "bad.yaml"))

    def test_interpolation_in_config(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                vars:
                  PROMPT: hello
            """)
            + _agents_yaml(_agent_yaml(prompt="'${PROMPT}'"))
        )
        assert load_config(cfg).agents["a"].system_prompt == "hello"

    def test_broken_model_ref_raises(self, write_config):
        cfg = write_config(_agents_yaml(_agent_yaml(model="nonexistent")))
        with pytest.raises(ValueError, match=r"references model.*nonexistent"):
            load_config(cfg)

    def test_broken_mcp_client_ref_raises(self, write_config):
        cfg = write_config(_agents_yaml(_agent_yaml(mcp=["missing_client"])))
        with pytest.raises(ValueError, match=r"references MCP client.*missing_client"):
            load_config(cfg)

    def test_broken_orchestration_delegate_ref(self, write_config):
        cfg = write_config(
            _agents_yaml(_agent_yaml("parent"))
            + _delegate_yaml("parent", [("ghost", "does not exist")])
        )
        with pytest.raises(ValueError, match=r"ghost.*is not defined"):
            load_config(cfg)

    def test_self_delegation_rejected(self, write_config):
        cfg = write_config(_agents_yaml(_agent_yaml("a")) + _delegate_yaml("a", [("a", "self")]))
        with pytest.raises(ValueError, match="delegates to itself"):
            load_config(cfg)

    def test_strip_anchors(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                x-base: &base
                  system_prompt: shared
                agents:
                  a:
                    <<: *base
                entry: a
            """)
        )
        config = load_config(cfg)
        assert "x-base" not in str(config.agents)
        assert "a" in config.agents


# ── env variable interpolation ────────────────────────────────────────────


class TestEnvVariableInterpolation:
    def test_env_var_interpolation(self, write_config, monkeypatch):
        monkeypatch.setenv("MY_PROMPT", "from-env")
        cfg = write_config(_agents_yaml(_agent_yaml(prompt="'${MY_PROMPT}'")))
        assert load_config(cfg).agents["a"].system_prompt == "from-env"


class TestEnvBlock:
    """Tests that env: block is ignored (feature removed)."""

    def test_no_env_block_is_fine(self, write_config):
        config = load_config(write_config(_minimal_yaml()))
        assert "a" in config.agents


# ── multi-source config merging ───────────────────────────────────────────


class TestMultiSourceConfig:
    """Tests for multi-file / multi-string config merging."""

    def test_single_file_still_works(self, simple_config_yaml):
        assert "assistant" in load_config(simple_config_yaml).agents

    def test_single_yaml_string(self):
        config = load_config(_minimal_yaml("hello"))
        assert config.agents["a"].system_prompt == "hello"

    def test_list_of_files(self, write_config):
        f1 = write_config(_agents_yaml(_agent_yaml()), "agents.yaml")
        f2 = write_config(
            textwrap.dedent("""\
                models:
                  default:
                    provider: bedrock
                    model_id: claude
                entry: a
            """),
            "models.yaml",
        )
        config = load_config([f1, f2])
        assert "a" in config.agents
        assert "default" in config.models

    def test_list_of_yaml_strings(self):
        config = load_config(
            [
                _agents_yaml(_agent_yaml()),
                _agents_yaml(_agent_yaml("b", "bye"), entry="a"),
            ]
        )
        assert "a" in config.agents
        assert "b" in config.agents

    def test_mixed_files_and_strings(self, write_config):
        f = write_config(_agents_yaml(_agent_yaml(prompt="from file")), "agents.yaml")
        config = load_config([f, _agents_yaml(_agent_yaml("b", "from string"), entry="a")])
        assert config.agents["a"].system_prompt == "from file"
        assert config.agents["b"].system_prompt == "from string"

    def test_merge_all_collection_sections(self, write_config):
        f1 = write_config(
            textwrap.dedent("""\
                models:
                  m1:
                    provider: bedrock
                    model_id: claude
            """)
            + _agents_yaml(_agent_yaml("agent1", model="m1")),
            "a.yaml",
        )
        f2 = write_config(
            textwrap.dedent("""\
                mcp_servers:
                  s1:
                    type: stdio
                    params:
                      command: echo
                mcp_clients:
                  c1:
                    server: s1
            """),
            "b.yaml",
        )
        f3 = write_config(
            _agents_yaml(_agent_yaml("agent2", model="m1", mcp=["c1"]), entry="agent1")
            + _swarm_yaml(["agent1", "agent2"], orch_name="orch1")
            + "entry: orch1\n",
            "c.yaml",
        )
        config = load_config([f1, f2, f3])
        assert set(config.models) == {"m1"}
        assert set(config.agents) == {"agent1", "agent2"}
        assert set(config.mcp_servers) == {"s1"}
        assert set(config.mcp_clients) == {"c1"}
        assert set(config.orchestrations) == {"orch1"}

    def test_duplicate_agent_names_raises(self, write_config):
        f1 = write_config(_agents_yaml(_agent_yaml("dupe", "first")), "a.yaml")
        f2 = write_config(_agents_yaml(_agent_yaml("dupe", "second")), "b.yaml")
        with pytest.raises(ValueError, match=r"Duplicate names in 'agents'.*dupe"):
            load_config([f1, f2])

    def test_duplicate_model_names_raises(self, write_config):
        f1 = write_config(
            textwrap.dedent("""\
                models:
                  m:
                    provider: bedrock
                    model_id: a
            """),
            "a.yaml",
        )
        f2 = write_config(
            textwrap.dedent("""\
                models:
                  m:
                    provider: bedrock
                    model_id: b
            """),
            "b.yaml",
        )
        with pytest.raises(ValueError, match=r"Duplicate names in 'models'.*m"):
            load_config([f1, f2])

    def test_duplicate_mcp_server_names_raises(self, write_config):
        f1 = write_config(
            textwrap.dedent("""\
                mcp_servers:
                  s:
                    type: stdio
            """),
            "a.yaml",
        )
        f2 = write_config(
            textwrap.dedent("""\
                mcp_servers:
                  s:
                    type: stdio
            """),
            "b.yaml",
        )
        with pytest.raises(ValueError, match=r"Duplicate names in 'mcp_servers'.*s"):
            load_config([f1, f2])

    def test_singleton_last_wins(self, write_config):
        f1 = write_config(_minimal_yaml() + "log_level: DEBUG\n", "a.yaml")
        f2 = write_config(
            _agents_yaml(_agent_yaml("b", "bye"), entry="a") + "log_level: ERROR\n", "b.yaml"
        )
        config = load_config([f1, f2])
        assert config.log_level == "ERROR"
        assert config.entry == "a"

    def test_per_source_vars_interpolation(self, write_config):
        f1 = write_config(
            textwrap.dedent("""\
                vars:
                  PROMPT: hello
            """)
            + _agents_yaml(_agent_yaml(prompt="'${PROMPT}'")),
            "a.yaml",
        )
        f2 = write_config(
            textwrap.dedent("""\
                vars:
                  PROMPT: goodbye
            """)
            + _agents_yaml(_agent_yaml("b", "'${PROMPT}'"), entry="a"),
            "b.yaml",
        )
        config = load_config([f1, f2])
        assert config.agents["a"].system_prompt == "hello"
        assert config.agents["b"].system_prompt == "goodbye"

    def test_per_source_anchors(self, write_config):
        f1 = write_config(
            textwrap.dedent("""\
                x-base: &base
                  system_prompt: shared
                agents:
                  a:
                    <<: *base
            """),
            "a.yaml",
        )
        f2 = write_config(_agents_yaml(_agent_yaml("b", "standalone"), entry="a"), "b.yaml")
        config = load_config([f1, f2])
        assert config.agents["a"].system_prompt == "shared"
        assert config.agents["b"].system_prompt == "standalone"

    def test_cross_ref_validation_after_merge(self, write_config):
        f1 = write_config(
            textwrap.dedent("""\
                models:
                  m:
                    provider: bedrock
                    model_id: claude
            """),
            "models.yaml",
        )
        f2 = write_config(_agents_yaml(_agent_yaml(model="m")), "agents.yaml")
        config = load_config([f1, f2])
        assert config.agents["a"].model == "m"

    def test_cross_ref_broken_after_merge_raises(self, write_config):
        f1 = write_config(_agents_yaml(_agent_yaml(model="missing_model")), "agents.yaml")
        with pytest.raises(ValueError, match="references model.*missing_model"):
            load_config([f1])

    def test_path_not_found_raises(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(Path("/nonexistent/config.yaml"))

    def test_invalid_yaml_string_raises(self):
        with pytest.raises(ValueError, match="YAML mapping"):
            load_config("just a plain string\n")


# ── name sanitization integration ─────────────────────────────────────────


class TestNameSanitization:
    """Integration tests: names are sanitized during config loading."""

    def test_spaces_replaced_with_underscores(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                agents:
                  'Database Analyzer':
                    system_prompt: hi
                entry: 'Database Analyzer'
            """)
        )
        config = load_config(cfg)
        assert "Database_Analyzer" in config.agents
        assert "Database Analyzer" not in config.agents

    def test_special_chars_sanitized(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                agents:
                  'my.agent@v2':
                    system_prompt: hi
                entry: 'my.agent@v2'
            """)
        )
        assert "my_agent_v2" in load_config(cfg).agents

    def test_valid_name_unchanged(self, write_config):
        assert "valid_name" in load_config(write_config(_minimal_yaml(entry="valid_name"))).agents

    def test_entry_ref_updated(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                agents:
                  'My Agent':
                    system_prompt: hi
                entry: 'My Agent'
            """)
        )
        config = load_config(cfg)
        assert config.entry == "My_Agent"
        assert "My_Agent" in config.agents

    def test_model_ref_updated(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                models:
                  'My Model':
                    provider: bedrock
                    model_id: claude
            """)
            + _agents_yaml(_agent_yaml(model="'My Model'"))
        )
        config = load_config(cfg)
        assert "My_Model" in config.models
        assert config.agents["a"].model == "My_Model"

    def test_mcp_ref_updated(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                mcp_servers:
                  'My Server':
                    type: stdio
                    params:
                      command: echo
                mcp_clients:
                  'My Client':
                    server: 'My Server'
            """)
            + _agents_yaml(_agent_yaml(mcp=["'My Client'"]))
        )
        config = load_config(cfg)
        assert "My_Server" in config.mcp_servers
        assert "My_Client" in config.mcp_clients
        assert config.mcp_clients["My_Client"].server == "My_Server"
        assert config.agents["a"].mcp == ["My_Client"]

    def test_delegate_orchestration_refs_updated(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                agents:
                  'Agent One':
                    system_prompt: hi
                  'Agent Two':
                    system_prompt: bye
            """)
            + _delegate_yaml("'Agent One'", [("'Agent Two'", "helper")])
            + "entry: main\n"
        )
        config = load_config(cfg)
        assert "Agent_One" in config.agents
        orch = config.orchestrations["main"]
        assert isinstance(orch, DelegateOrchestrationDef)
        assert orch.entry_name == "Agent_One"
        assert orch.connections[0].agent == "Agent_Two"

    def test_swarm_refs_updated(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                agents:
                  'Agent A':
                    system_prompt: hi
                  'Agent B':
                    system_prompt: bye
                orchestrations:
                  main:
                    mode: swarm
                    entry_name: 'Agent A'
                    agents:
                      - 'Agent A'
                      - 'Agent B'
                entry: 'Agent A'
            """)
        )
        config = load_config(cfg)
        orch = config.orchestrations["main"]
        assert isinstance(orch, SwarmOrchestrationDef)
        assert orch.agents == ["Agent_A", "Agent_B"]

    def test_graph_refs_updated(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                agents:
                  'Agent A':
                    system_prompt: hi
                  'Agent B':
                    system_prompt: bye
                orchestrations:
                  main:
                    mode: graph
                    entry_name: 'Agent A'
                    edges:
                      - from: 'Agent A'
                        to: 'Agent B'
                entry: 'Agent A'
            """)
        )
        config = load_config(cfg)
        orch = config.orchestrations["main"]
        assert isinstance(orch, GraphOrchestrationDef)
        assert orch.edges[0].from_agent == "Agent_A"
        assert orch.edges[0].to_agent == "Agent_B"

    def test_duplicate_after_sanitization_raises(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                agents:
                  'my agent':
                    system_prompt: hi
                  my_agent:
                    system_prompt: bye
            """)
        )
        with pytest.raises(ValueError, match="Duplicate name.*after sanitization"):
            load_config(cfg)

    def test_empty_after_sanitization_raises(self, write_config):
        with pytest.raises(ValueError, match="empty after sanitization"):
            load_config(
                write_config(
                    textwrap.dedent("""\
                        agents:
                          '...':
                            system_prompt: hi
                    """)
                )
            )


# ── ConfigurationError messages ───────────────────────────────────────────


class TestConfigurationErrorMessages:
    """ConfigurationError is raised for all config problems — never raw Pydantic dumps."""

    def test_invalid_yaml_in_file_raises_configuration_error_with_path(self, write_config):
        f = write_config("key: [\nunot closed\n", "bad.yaml")
        with pytest.raises(ConfigurationError, match=re.escape(str(f))):
            load_config(f)

    def test_invalid_yaml_in_inline_string_raises_configuration_error(self):
        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            load_config("key: [unclosed\n")

    def test_pydantic_validation_error_raises_configuration_error(self, write_config):
        cfg = write_config(_minimal_yaml() + "log_level: 42\n")
        with pytest.raises(ConfigurationError, match=r"log_level"):
            load_config(cfg)

    def test_pydantic_error_message_has_no_pydantic_dump(self, write_config):
        cfg = write_config(_minimal_yaml() + "log_level: 42\n")
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(cfg)
        msg = str(exc_info.value)
        assert "For further information" not in msg
        assert "Check your YAML configuration file." in msg

    def test_unknown_model_ref_raises_configuration_error_listing_models(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                models:
                  gpt4:
                    provider: openai
                    model_id: gpt-4
            """)
            + _agents_yaml(_agent_yaml(model="TYPO"))
        )
        with pytest.raises(ConfigurationError, match=r"TYPO"):
            load_config(cfg)

    def test_unknown_mcp_client_ref_raises_configuration_error_listing_clients(self, write_config):
        cfg = write_config(_agents_yaml(_agent_yaml(mcp=["GHOST_CLIENT"])))
        with pytest.raises(ConfigurationError, match=r"GHOST_CLIENT"):
            load_config(cfg)

    def test_configuration_error_is_subclass_of_value_error(self):
        assert issubclass(ConfigurationError, ValueError)


# ── path rewriting integration ────────────────────────────────────────────


class TestLoadConfigPathRewriting:
    """Integration tests: load_config rewrites relative filesystem paths."""

    def test_load_config_rewrites_tool_paths(self, tmp_path):
        tools_file = tmp_path / "tools.py"
        tools_file.write_text("")
        config_file = tmp_path / "config.yaml"
        config_file.write_text(_agents_yaml(_agent_yaml(tools=["./tools.py"]), entry="a"))
        config = load_config(config_file)
        tool_spec = config.agents["a"].tools[0]
        assert Path(tool_spec).is_absolute()
        assert Path(tool_spec) == tools_file.resolve()

    def test_load_config_rewrites_tool_with_function(self, write_config):
        cfg = write_config(_agents_yaml(_agent_yaml(tools=["./tools.py:my_func"])))
        config = load_config(cfg)
        abs_part, _, func_part = config.agents["a"].tools[0].rpartition(":")
        assert Path(abs_part).is_absolute()
        assert func_part == "my_func"

    def test_load_config_rewrites_hook_type(self, write_config):
        cfg = write_config(
            textwrap.dedent("""\
                agents:
                  analyst:
                    hooks:
                      - type: ./hooks.py:MyGuard
                    system_prompt: hi
                entry: analyst
            """)
        )
        config = load_config(cfg)
        hook = config.agents["analyst"].hooks[0]
        assert not isinstance(hook, str)
        hook_type = hook.type
        assert Path(hook_type.rpartition(":")[0]).is_absolute()
        assert hook_type.endswith(":MyGuard")
