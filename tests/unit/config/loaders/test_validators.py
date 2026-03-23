"""Tests for config.loaders.validators — _validate_references and orchestration checks."""

from __future__ import annotations

import pytest

from strands_compose.config.loaders import load_config


class TestValidateMCPClientServerRef:
    def test_mcp_client_broken_server_ref(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text(
            "mcp_clients:\n"
            "  my_client:\n"
            "    server: nonexistent_server\n"
            "agents:\n"
            "  a:\n"
            "    system_prompt: hi\n"
            "entry: a\n"
        )
        with pytest.raises(ValueError, match=r"references server.*nonexistent_server"):
            load_config(f)


class TestValidateOrchestrationDelegateParent:
    def test_delegate_entry_not_in_agents(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text(
            "agents:\n"
            "  child:\n"
            "    system_prompt: hi\n"
            "orchestrations:\n"
            "  main:\n"
            "    mode: delegate\n"
            "    entry_name: ghost_parent\n"
            "    connections:\n"
            "      - agent: child\n"
            "        description: test\n"
            "entry: main\n"
        )
        with pytest.raises(ValueError, match=r"ghost_parent.*is not defined"):
            load_config(f)


class TestValidateSwarmOrchestration:
    def test_swarm_invalid_agent_ref(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text(
            "agents:\n"
            "  a:\n"
            "    system_prompt: hi\n"
            "orchestrations:\n"
            "  main:\n"
            "    mode: swarm\n"
            "    entry_name: a\n"
            "    agents:\n"
            "      - a\n"
            "      - ghost\n"
            "entry: a\n"
        )
        with pytest.raises(ValueError, match=r"Swarm agent.*ghost.*is not defined"):
            load_config(f)

    def test_swarm_valid(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text(
            "agents:\n"
            "  a:\n"
            "    system_prompt: hi\n"
            "  b:\n"
            "    system_prompt: hi\n"
            "orchestrations:\n"
            "  main:\n"
            "    mode: swarm\n"
            "    entry_name: a\n"
            "    agents:\n"
            "      - a\n"
            "      - b\n"
            "entry: a\n"
        )
        config = load_config(f)
        assert "main" in config.orchestrations
        assert config.orchestrations["main"].mode == "swarm"


class TestValidateGraphOrchestration:
    def test_graph_invalid_from_agent(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text(
            "agents:\n"
            "  a:\n"
            "    system_prompt: hi\n"
            "orchestrations:\n"
            "  main:\n"
            "    mode: graph\n"
            "    entry_name: a\n"
            "    edges:\n"
            "      - from: ghost\n"
            "        to: a\n"
            "entry: a\n"
        )
        with pytest.raises(ValueError, match=r"Graph edge source.*ghost.*is not defined"):
            load_config(f)

    def test_graph_invalid_to_agent(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text(
            "agents:\n"
            "  a:\n"
            "    system_prompt: hi\n"
            "orchestrations:\n"
            "  main:\n"
            "    mode: graph\n"
            "    entry_name: a\n"
            "    edges:\n"
            "      - from: a\n"
            "        to: ghost\n"
            "entry: a\n"
        )
        with pytest.raises(ValueError, match=r"Graph edge target.*ghost.*is not defined"):
            load_config(f)

    def test_graph_valid(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text(
            "agents:\n"
            "  a:\n"
            "    system_prompt: hi\n"
            "  b:\n"
            "    system_prompt: hi\n"
            "orchestrations:\n"
            "  main:\n"
            "    mode: graph\n"
            "    entry_name: a\n"
            "    edges:\n"
            "      - from: a\n"
            "        to: b\n"
            "entry: a\n"
        )
        config = load_config(f)
        assert "main" in config.orchestrations
        assert config.orchestrations["main"].mode == "graph"


class TestNamedOrchestrationsValidation:
    """Tests for named orchestrations: validation in _validate_references."""

    def test_named_orch_valid_refs(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text(
            "agents:\n"
            "  a:\n"
            "    system_prompt: hi\n"
            "  b:\n"
            "    system_prompt: hi\n"
            "orchestrations:\n"
            "  my_swarm:\n"
            "    mode: swarm\n"
            "    entry_name: a\n"
            "    agents: [a, b]\n"
            "entry: my_swarm\n"
        )
        config = load_config(f)
        assert "my_swarm" in config.orchestrations

    def test_named_orch_cross_reference(self, tmp_path):
        """Named orchestrations can reference other orchestrations."""
        f = tmp_path / "config.yaml"
        f.write_text(
            "agents:\n"
            "  a:\n"
            "    system_prompt: hi\n"
            "  b:\n"
            "    system_prompt: hi\n"
            "  reviewer:\n"
            "    system_prompt: hi\n"
            "orchestrations:\n"
            "  team:\n"
            "    mode: swarm\n"
            "    entry_name: a\n"
            "    agents: [a, b]\n"
            "  pipeline:\n"
            "    mode: graph\n"
            "    entry_name: team\n"
            "    edges:\n"
            "      - from: team\n"
            "        to: reviewer\n"
            "entry: pipeline\n"
        )
        config = load_config(f)
        assert "team" in config.orchestrations
        assert "pipeline" in config.orchestrations

    def test_named_orch_invalid_ref_raises(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text(
            "agents:\n"
            "  a:\n"
            "    system_prompt: hi\n"
            "orchestrations:\n"
            "  my_swarm:\n"
            "    mode: swarm\n"
            "    entry_name: a\n"
            "    agents: [a, ghost]\n"
            "entry: my_swarm\n"
        )
        with pytest.raises(ValueError, match=r"ghost.*is not defined"):
            load_config(f)

    def test_named_orch_with_entry(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text(
            "agents:\n"
            "  a:\n"
            "    system_prompt: hi\n"
            "  b:\n"
            "    system_prompt: hi\n"
            "orchestrations:\n"
            "  my_swarm:\n"
            "    mode: swarm\n"
            "    entry_name: a\n"
            "    agents: [a, b]\n"
            "entry: my_swarm\n"
        )
        config = load_config(f)
        assert config.entry == "my_swarm"
