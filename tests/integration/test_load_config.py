"""Integration tests for load_config() — full parse → validate → AppConfig pipeline."""

from __future__ import annotations

import pytest

from strands_compose.config import load_config
from strands_compose.config.schema import (
    AppConfig,
    DelegateOrchestrationDef,
    GraphOrchestrationDef,
    SwarmOrchestrationDef,
)
from strands_compose.exceptions import SchemaValidationError


@pytest.mark.integration
class TestLoadConfigMinimal:
    """Load the minimal fixture and verify the AppConfig."""

    def test_loads_minimal_config(self, fixture_path):
        config = load_config(fixture_path("minimal.yaml"))
        assert isinstance(config, AppConfig)
        assert "greeter" in config.agents
        assert config.entry == "greeter"

    def test_minimal_agent_has_system_prompt(self, fixture_path):
        config = load_config(fixture_path("minimal.yaml"))
        assert config.agents["greeter"].system_prompt == "You are a helpful assistant."

    def test_minimal_has_no_orchestrations(self, fixture_path):
        config = load_config(fixture_path("minimal.yaml"))
        assert config.orchestrations == {}

    def test_minimal_has_no_models(self, fixture_path):
        config = load_config(fixture_path("minimal.yaml"))
        assert config.models == {}


@pytest.mark.integration
class TestLoadConfigWithModel:
    """Load config with explicit model definition."""

    def test_loads_model(self, fixture_path):
        config = load_config(fixture_path("with_model.yaml"))
        assert "bedrock_model" in config.models
        assert config.models["bedrock_model"].provider == "bedrock"

    def test_agent_references_model(self, fixture_path):
        config = load_config(fixture_path("with_model.yaml"))
        assert config.agents["assistant"].model == "bedrock_model"


@pytest.mark.integration
class TestLoadConfigDelegate:
    """Load delegate orchestration config."""

    def test_loads_delegate_orchestration(self, fixture_path):
        config = load_config(fixture_path("multi_agent_delegate.yaml"))
        assert "coordinator" in config.orchestrations
        orch = config.orchestrations["coordinator"]
        assert isinstance(orch, DelegateOrchestrationDef)

    def test_delegate_has_connections(self, fixture_path):
        config = load_config(fixture_path("multi_agent_delegate.yaml"))
        orch = config.orchestrations["coordinator"]
        assert isinstance(orch, DelegateOrchestrationDef)
        assert len(orch.connections) == 1
        assert orch.connections[0].agent == "researcher"

    def test_delegate_entry_name(self, fixture_path):
        config = load_config(fixture_path("multi_agent_delegate.yaml"))
        orch = config.orchestrations["coordinator"]
        assert isinstance(orch, DelegateOrchestrationDef)
        assert orch.entry_name == "writer"

    def test_delegate_all_agents_defined(self, fixture_path):
        config = load_config(fixture_path("multi_agent_delegate.yaml"))
        assert "researcher" in config.agents
        assert "writer" in config.agents


@pytest.mark.integration
class TestLoadConfigSwarm:
    """Load swarm orchestration config."""

    def test_loads_swarm_orchestration(self, fixture_path):
        config = load_config(fixture_path("swarm.yaml"))
        assert "team" in config.orchestrations
        orch = config.orchestrations["team"]
        assert isinstance(orch, SwarmOrchestrationDef)

    def test_swarm_has_agents_list(self, fixture_path):
        config = load_config(fixture_path("swarm.yaml"))
        orch = config.orchestrations["team"]
        assert isinstance(orch, SwarmOrchestrationDef)
        assert orch.agents == ["analyst", "reporter"]

    def test_swarm_entry_name(self, fixture_path):
        config = load_config(fixture_path("swarm.yaml"))
        orch = config.orchestrations["team"]
        assert isinstance(orch, SwarmOrchestrationDef)
        assert orch.entry_name == "analyst"

    def test_swarm_max_handoffs(self, fixture_path):
        config = load_config(fixture_path("swarm.yaml"))
        orch = config.orchestrations["team"]
        assert isinstance(orch, SwarmOrchestrationDef)
        assert orch.max_handoffs == 10


@pytest.mark.integration
class TestLoadConfigGraph:
    """Load graph orchestration config."""

    def test_loads_graph_orchestration(self, fixture_path):
        config = load_config(fixture_path("graph.yaml"))
        assert "pipeline" in config.orchestrations
        orch = config.orchestrations["pipeline"]
        assert isinstance(orch, GraphOrchestrationDef)

    def test_graph_has_edges(self, fixture_path):
        config = load_config(fixture_path("graph.yaml"))
        orch = config.orchestrations["pipeline"]
        assert isinstance(orch, GraphOrchestrationDef)
        assert len(orch.edges) == 2

    def test_graph_edge_structure(self, fixture_path):
        config = load_config(fixture_path("graph.yaml"))
        orch = config.orchestrations["pipeline"]
        assert isinstance(orch, GraphOrchestrationDef)
        edge = orch.edges[0]
        assert edge.from_agent == "collector"
        assert edge.to_agent == "analyzer"


@pytest.mark.integration
class TestLoadConfigNestedOrchestration:
    """Load nested orchestration config."""

    def test_loads_nested_orchestrations(self, fixture_path):
        config = load_config(fixture_path("nested_orchestration.yaml"))
        assert "writing_team" in config.orchestrations
        assert "full_pipeline" in config.orchestrations

    def test_nested_entry_is_outer(self, fixture_path):
        config = load_config(fixture_path("nested_orchestration.yaml"))
        assert config.entry == "full_pipeline"

    def test_inner_orchestration_is_delegate(self, fixture_path):
        config = load_config(fixture_path("nested_orchestration.yaml"))
        inner = config.orchestrations["writing_team"]
        assert isinstance(inner, DelegateOrchestrationDef)
        assert inner.entry_name == "writer"

    def test_outer_references_inner(self, fixture_path):
        config = load_config(fixture_path("nested_orchestration.yaml"))
        outer = config.orchestrations["full_pipeline"]
        assert isinstance(outer, DelegateOrchestrationDef)
        assert any(c.agent == "writing_team" for c in outer.connections)


@pytest.mark.integration
class TestLoadConfigWithHooks:
    """Load config with hook definitions."""

    def test_loads_hooks(self, fixture_path):
        config = load_config(fixture_path("with_hooks.yaml"))
        agent = config.agents["assistant"]
        assert len(agent.hooks) == 1

    def test_hook_type_resolved(self, fixture_path):
        config = load_config(fixture_path("with_hooks.yaml"))
        hook = config.agents["assistant"].hooks[0]
        assert not isinstance(hook, str)
        assert hook.type == "strands_compose.hooks:MaxToolCallsGuard"

    def test_hook_params(self, fixture_path):
        config = load_config(fixture_path("with_hooks.yaml"))
        hook = config.agents["assistant"].hooks[0]
        assert not isinstance(hook, str)
        assert hook.params == {"max_calls": 5}


@pytest.mark.integration
class TestLoadConfigWithVars:
    """Load config with variable interpolation."""

    def test_vars_interpolated_in_model(self, fixture_path):
        config = load_config(fixture_path("with_vars.yaml"))
        assert config.models["main_model"].provider == "bedrock"
        assert config.models["main_model"].model_id == "anthropic.claude-3-haiku-20240307-v1:0"


@pytest.mark.integration
class TestLoadConfigWithSessionManager:
    """Load config with session manager."""

    def test_session_manager_loaded(self, fixture_path):
        config = load_config(fixture_path("with_session_manager.yaml"))
        assert config.session_manager is not None
        assert config.session_manager.provider == "file"

    def test_session_manager_params(self, fixture_path):
        config = load_config(fixture_path("with_session_manager.yaml"))
        assert config.session_manager is not None
        assert config.session_manager.params["session_id"] == "test-session"


@pytest.mark.integration
class TestLoadConfigComplex:
    """Load the complex full config with all features."""

    def test_loads_complex_config(self, fixture_path):
        config = load_config(fixture_path("complex_full.yaml"))
        assert isinstance(config, AppConfig)

    def test_complex_has_two_models(self, fixture_path):
        config = load_config(fixture_path("complex_full.yaml"))
        assert "fast_model" in config.models
        assert "smart_model" in config.models

    def test_complex_has_four_agents(self, fixture_path):
        config = load_config(fixture_path("complex_full.yaml"))
        assert len(config.agents) == 4

    def test_complex_has_two_orchestrations(self, fixture_path):
        config = load_config(fixture_path("complex_full.yaml"))
        assert len(config.orchestrations) == 2

    def test_complex_writing_team_is_delegate(self, fixture_path):
        config = load_config(fixture_path("complex_full.yaml"))
        wt = config.orchestrations["writing_team"]
        assert isinstance(wt, DelegateOrchestrationDef)

    def test_complex_content_pipeline_is_graph(self, fixture_path):
        config = load_config(fixture_path("complex_full.yaml"))
        cp = config.orchestrations["content_pipeline"]
        assert isinstance(cp, GraphOrchestrationDef)

    def test_complex_vars_interpolated(self, fixture_path):
        config = load_config(fixture_path("complex_full.yaml"))
        assert config.models["fast_model"].model_id == "anthropic.claude-3-haiku-20240307-v1:0"

    def test_complex_entry_is_graph(self, fixture_path):
        config = load_config(fixture_path("complex_full.yaml"))
        assert config.entry == "content_pipeline"

    def test_complex_agent_has_hooks(self, fixture_path):
        config = load_config(fixture_path("complex_full.yaml"))
        writer = config.agents["writer"]
        assert len(writer.hooks) == 1


@pytest.mark.integration
class TestLoadConfigMultipleFiles:
    """Test loading and merging multiple config files."""

    def test_merge_two_configs(self, tmp_path):
        agents_file = tmp_path / "agents.yaml"
        agents_file.write_text("agents:\n  a:\n    system_prompt: hello\nentry: a\n")
        extra_file = tmp_path / "extra.yaml"
        extra_file.write_text("agents:\n  b:\n    system_prompt: world\n")
        config = load_config([str(agents_file), str(extra_file)])
        assert "a" in config.agents
        assert "b" in config.agents

    def test_merge_duplicate_agents_raises(self, tmp_path):
        f1 = tmp_path / "a.yaml"
        f1.write_text("agents:\n  dup:\n    system_prompt: hi\nentry: dup\n")
        f2 = tmp_path / "b.yaml"
        f2.write_text("agents:\n  dup:\n    system_prompt: bye\n")
        with pytest.raises(ValueError, match="Duplicate"):
            load_config([str(f1), str(f2)])


@pytest.mark.integration
class TestLoadConfigErrorCases:
    """Test error handling in load_config."""

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path.yaml")

    def test_invalid_yaml_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("{{not valid yaml")
        with pytest.raises(Exception):
            load_config(str(bad))

    def test_missing_entry_raises(self, tmp_path):
        f = tmp_path / "noentry.yaml"
        f.write_text("agents:\n  a:\n    system_prompt: hi\nentry: missing\n")
        with pytest.raises((ValueError, SchemaValidationError)):
            load_config(str(f))

    def test_empty_config_raises(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("{}")
        with pytest.raises((ValueError, SchemaValidationError)):
            load_config(str(f))
