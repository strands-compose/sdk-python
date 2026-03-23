"""Tests for core.config.schema — Pydantic model validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from strands_compose.config.schema import (
    AgentDef,
    AppConfig,
    DelegateConnectionDef,
    DelegateOrchestrationDef,
    MCPClientDef,
    MCPServerDef,
    SwarmOrchestrationDef,
)


class TestMCPClientDef:
    def test_exactly_one_connection_mode_required(self):
        with pytest.raises(ValidationError, match="exactly one"):
            MCPClientDef()

    def test_multiple_modes_rejected(self):
        with pytest.raises(ValidationError, match="exactly one"):
            MCPClientDef(server="s", url="http://x")

    def test_valid_server_mode(self):
        c = MCPClientDef(server="my-server")
        assert c.server == "my-server"

    def test_valid_url_mode(self):
        c = MCPClientDef(url="http://localhost:8000")
        assert c.url == "http://localhost:8000"

    def test_valid_command_mode(self):
        c = MCPClientDef(command=["python", "-m", "server"])
        assert c.command == ["python", "-m", "server"]


class TestAgentDef:
    def test_defaults(self):
        a = AgentDef()
        assert a.tools == []
        assert a.hooks == []
        assert a.mcp == []
        assert a.model is None

    def test_agent_kwargs_accepted(self):
        a = AgentDef(agent_kwargs={"retry": True})
        assert a.agent_kwargs == {"retry": True}

    def test_agent_kwargs_defaults_to_empty_dict(self):
        a = AgentDef()
        assert a.agent_kwargs == {}


class TestDelegateOrchestrationDef:
    def test_basic_construction(self):
        orch = DelegateOrchestrationDef(
            entry_name="parent",
            connections=[DelegateConnectionDef(agent="child", description="sub")],
        )
        assert orch.entry_name == "parent"
        assert len(orch.connections) == 1
        assert orch.session_manager is None
        assert orch.agent_kwargs == {}

    def test_session_manager_allowed(self):
        from strands_compose.config.schema import SessionManagerDef

        orch = DelegateOrchestrationDef(
            entry_name="parent",
            connections=[DelegateConnectionDef(agent="child", description="sub")],
            session_manager=SessionManagerDef(),
        )
        assert orch.session_manager is not None

    def test_agent_kwargs_override(self):
        orch = DelegateOrchestrationDef(
            entry_name="parent",
            connections=[DelegateConnectionDef(agent="child", description="sub")],
            agent_kwargs={"max_tool_calls": 50},
        )
        assert orch.agent_kwargs == {"max_tool_calls": 50}


class TestAppConfig:
    def test_entry_ref_validation(self):
        with pytest.raises(ValidationError, match=r"entry.*not defined"):
            AppConfig(
                agents={"a": AgentDef()},
                entry="nonexistent",
            )

    def test_valid_config(self):
        cfg = AppConfig(
            agents={"assistant": AgentDef(system_prompt="Hi")},
            entry="assistant",
        )
        assert cfg.entry == "assistant"

    def test_empty_config_missing_entry_raises(self):
        with pytest.raises(ValidationError, match="entry"):
            AppConfig(entry="nonexistent")

    def test_version_defaults_to_one(self):
        cfg = AppConfig(agents={"a": AgentDef()}, entry="a")
        assert cfg.version == "1"

    def test_version_can_be_set(self):
        cfg = AppConfig(agents={"a": AgentDef()}, entry="a", version="1")
        assert cfg.version == "1"


class TestOrchestrations:
    def test_orchestrations_ok(self):
        cfg = AppConfig(
            agents={"a": AgentDef(), "b": AgentDef()},
            orchestrations={
                "my_swarm": SwarmOrchestrationDef(entry_name="a", agents=["a", "b"]),
            },
            entry="my_swarm",
        )
        assert "my_swarm" in cfg.orchestrations


class TestNameCollisionValidation:
    def test_agent_orch_name_collision_rejected(self):
        with pytest.raises(ValidationError, match="Name collision"):
            AppConfig(
                agents={"overlap": AgentDef()},
                orchestrations={
                    "overlap": SwarmOrchestrationDef(entry_name="overlap", agents=["overlap"]),
                },
                entry="overlap",
            )

    def test_no_collision_ok(self):
        cfg = AppConfig(
            agents={"agent1": AgentDef(), "agent2": AgentDef()},
            orchestrations={
                "my_swarm": SwarmOrchestrationDef(entry_name="agent1", agents=["agent1", "agent2"]),
            },
            entry="my_swarm",
        )
        assert "agent1" in cfg.agents
        assert "my_swarm" in cfg.orchestrations

    def test_agent_mcp_server_same_name_allowed(self):
        # mcp_servers are a separate namespace from agents — sharing a name is fine
        cfg = AppConfig(
            agents={"db": AgentDef()},
            mcp_servers={"db": MCPServerDef(type="my.module:Factory")},
            entry="db",
        )
        assert "db" in cfg.agents
        assert "db" in cfg.mcp_servers

    def test_mcp_server_mcp_client_same_name_allowed(self):
        # mcp_servers and mcp_clients are independent namespaces — sharing a name is fine
        cfg = AppConfig(
            mcp_servers={"postgres": MCPServerDef(type="my.module:Factory")},
            mcp_clients={"postgres": MCPClientDef(url="http://localhost:8080")},
            agents={"a": AgentDef()},
            entry="a",
        )
        assert "postgres" in cfg.mcp_servers
        assert "postgres" in cfg.mcp_clients


class TestEntryRefValidation:
    def test_entry_can_reference_orchestration(self):
        cfg = AppConfig(
            agents={"a": AgentDef(), "b": AgentDef()},
            orchestrations={
                "my_swarm": SwarmOrchestrationDef(entry_name="a", agents=["a", "b"]),
            },
            entry="my_swarm",
        )
        assert cfg.entry == "my_swarm"

    def test_entry_invalid_ref_rejected(self):
        with pytest.raises(ValidationError, match="not defined"):
            AppConfig(
                agents={"a": AgentDef()},
                orchestrations={
                    "my_swarm": SwarmOrchestrationDef(entry_name="a", agents=["a"]),
                },
                entry="nonexistent",
            )
