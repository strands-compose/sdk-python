"""Tests for core.config.resolvers.agents — resolve_agents, resolve_orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from strands import Agent as _RealAgent

from strands_compose.config.resolvers.agents import resolve_agents
from strands_compose.config.resolvers.orchestrations import resolve_orchestrations
from strands_compose.config.schema import (
    AgentDef,
    ConversationManagerDef,
    HookDef,
    ModelDef,
    SessionManagerDef,
    SwarmOrchestrationDef,
)
from strands_compose.exceptions import ConfigurationError


class TestResolveAgents:
    def test_simple_agent_with_model_ref(self, patch_agent_init):
        agent_def = AgentDef(model="my-model", system_prompt="You are helpful")
        models = {"my-model": MagicMock()}
        result = resolve_agents(
            {"main": agent_def},
            models=models,  # type: ignore[arg-type]
            mcp_clients={},
            session_manager=None,
        )
        assert "main" in result
        agent = result["main"]
        assert isinstance(agent, _RealAgent)
        assert agent._init_kwargs["model"] is models["my-model"]  # type: ignore[unresolved-attribute]
        assert agent._init_kwargs["system_prompt"] == "You are helpful"  # type: ignore[unresolved-attribute]

    @patch("strands_compose.config.resolvers.agents.resolve_model")
    def test_agent_with_inline_model(self, mock_resolve_model, patch_agent_init):
        inline_model = ModelDef(provider="bedrock", model_id="nova-v1:0")
        agent_def = AgentDef(model=inline_model)
        result = resolve_agents(
            {"main": agent_def}, models={}, mcp_clients={}, session_manager=None
        )
        assert "main" in result
        mock_resolve_model.assert_called_once_with(inline_model)

    def test_agent_with_no_model(self, patch_agent_init):
        agent_def = AgentDef()
        result = resolve_agents(
            {"main": agent_def}, models={}, mcp_clients={}, session_manager=None
        )
        assert "main" in result
        assert result["main"]._init_kwargs["model"] is None  # type: ignore[unresolved-attribute]

    @patch("strands_compose.config.resolvers.agents.resolve_tools")
    def test_agent_with_tools(self, mock_resolve_tools, patch_agent_init):
        tool_obj = MagicMock()
        mock_resolve_tools.return_value = [tool_obj]
        agent_def = AgentDef(tools=["my.module:my_tool"])
        result = resolve_agents(
            {"main": agent_def}, models={}, mcp_clients={}, session_manager=None
        )
        assert "main" in result
        mock_resolve_tools.assert_called_once_with(["my.module:my_tool"])

    @patch("strands_compose.config.resolvers.agents.resolve_hook_entry")
    def test_agent_with_hooks(self, mock_resolve_hook, patch_agent_init):
        mock_hook = MagicMock()
        mock_resolve_hook.return_value = mock_hook
        hook_def = HookDef(type="strands_compose.hooks.max_calls_guard:MaxToolCallsGuard")
        agent_def = AgentDef(hooks=[hook_def])
        result = resolve_agents(
            {"main": agent_def}, models={}, mcp_clients={}, session_manager=None
        )
        assert "main" in result
        mock_resolve_hook.assert_called_once_with(hook_def)

    def test_agent_with_mcp_clients(self, patch_agent_init):
        mock_client = MagicMock()
        agent_def = AgentDef(mcp=["pg-client"])
        result = resolve_agents(
            {"main": agent_def},
            models={},
            mcp_clients={"pg-client": mock_client},
            session_manager=None,
        )
        assert "main" in result
        assert mock_client in result["main"]._init_kwargs["tools"]  # type: ignore[unresolved-attribute]

    @patch("strands_compose.config.resolvers.agents.load_object")
    def test_agent_with_custom_type(self, mock_import):
        mock_factory = MagicMock(return_value=MagicMock(spec=_RealAgent))
        mock_import.return_value = mock_factory
        agent_def = AgentDef(type="my.module:CustomAgent", agent_kwargs={"extra": "val"})
        result = resolve_agents(
            {"main": agent_def}, models={}, mcp_clients={}, session_manager=None
        )
        assert "main" in result
        mock_factory.assert_called_once()
        call_kwargs = mock_factory.call_args[1]
        assert call_kwargs["extra"] == "val"

    @patch("strands_compose.config.resolvers.agents.load_object")
    def test_custom_type_non_agent_raises(self, mock_import):
        mock_import.return_value = MagicMock(return_value="not_an_agent")
        agent_def = AgentDef(type="my.module:BadFactory")
        with pytest.raises(TypeError, match="expected strands.Agent"):
            resolve_agents({"main": agent_def}, models={}, mcp_clients={}, session_manager=None)

    def test_agent_without_conversation_manager_passes_none(self, patch_agent_init):
        """Agent without conversation_manager config passes None to Agent constructor."""
        agent_def = AgentDef()
        result = resolve_agents(
            {"main": agent_def}, models={}, mcp_clients={}, session_manager=None
        )
        assert result["main"]._init_kwargs["conversation_manager"] is None  # type: ignore[unresolved-attribute]

    @patch("strands_compose.config.resolvers.agents.resolve_conversation_manager")
    def test_agent_with_conversation_manager_resolves_and_passes(
        self, mock_resolve_cm, patch_agent_init
    ):
        """Agent with conversation_manager config resolves and passes to constructor."""
        mock_cm = MagicMock()
        mock_resolve_cm.return_value = mock_cm
        cm_def = ConversationManagerDef(
            type="strands.agent:SlidingWindowConversationManager",
            params={"should_truncate_results": False},
        )
        agent_def = AgentDef(conversation_manager=cm_def)
        result = resolve_agents(
            {"main": agent_def}, models={}, mcp_clients={}, session_manager=None
        )
        mock_resolve_cm.assert_called_once_with(cm_def)
        assert result["main"]._init_kwargs["conversation_manager"] is mock_cm  # type: ignore[unresolved-attribute]

    @patch("strands_compose.config.resolvers.agents.resolve_conversation_manager")
    @patch("strands_compose.config.resolvers.agents.load_object")
    def test_custom_factory_receives_resolved_conversation_manager(
        self, mock_import, mock_resolve_cm
    ):
        """Custom agent factory also receives the resolved conversation_manager."""
        mock_cm = MagicMock()
        mock_resolve_cm.return_value = mock_cm
        mock_factory = MagicMock(return_value=MagicMock(spec=_RealAgent))
        mock_import.return_value = mock_factory
        cm_def = ConversationManagerDef(
            type="strands.agent:NullConversationManager",
        )
        agent_def = AgentDef(type="my.module:CustomAgent", conversation_manager=cm_def)
        resolve_agents({"main": agent_def}, models={}, mcp_clients={}, session_manager=None)
        call_kwargs = mock_factory.call_args[1]
        assert call_kwargs["conversation_manager"] is mock_cm


class TestSwarmSessionGuard:
    """Tests for the fail-fast swarm + session manager conflict guard."""

    def test_swarm_agent_inherits_global_sm_raises_configuration_error(self, patch_agent_init):
        """Swarm agent that would inherit the global SM raises ConfigurationError."""
        global_sm = MagicMock()
        agent_def = AgentDef()  # session_manager NOT in model_fields_set
        with pytest.raises(ConfigurationError, match="global 'session_manager:'"):
            resolve_agents(
                {"node": agent_def},
                models={},
                mcp_clients={},
                session_manager=global_sm,
                swarm_agent_names={"node"},
            )

    @patch("strands_compose.config.resolvers.agents.resolve_session_manager")
    def test_swarm_agent_with_explicit_per_agent_sm_raises_configuration_error(
        self, mock_resolve_sm, patch_agent_init
    ):
        """Swarm agent with an explicit per-agent session_manager raises ConfigurationError."""
        mock_resolve_sm.return_value = MagicMock()
        sm_def = SessionManagerDef(provider="file")
        agent_def = AgentDef(session_manager=sm_def)
        with pytest.raises(ConfigurationError, match="per-agent 'session_manager:'"):
            resolve_agents(
                {"node": agent_def},
                models={},
                mcp_clients={},
                session_manager=None,
                swarm_agent_names={"node"},
            )

    def test_swarm_agent_with_explicit_null_sm_opts_out_and_succeeds(self, patch_agent_init):
        """Swarm agent with session_manager: ~ (explicit None) opts out and is built."""
        global_sm = MagicMock()
        agent_def = AgentDef(session_manager=None)  # explicit None -> opt-out
        assert "session_manager" in agent_def.model_fields_set
        result = resolve_agents(
            {"node": agent_def},
            models={},
            mcp_clients={},
            session_manager=global_sm,
            swarm_agent_names={"node"},
        )
        assert "node" in result
        assert result["node"]._init_kwargs["session_manager"] is None  # type: ignore[unresolved-attribute]

    def test_non_swarm_agent_inherits_global_sm(self, patch_agent_init):
        """Non-swarm agent with no per-agent SM inherits the global session manager."""
        global_sm = MagicMock()
        agent_def = AgentDef()
        result = resolve_agents(
            {"main": agent_def},
            models={},
            mcp_clients={},
            session_manager=global_sm,
        )
        assert result["main"]._init_kwargs["session_manager"] is global_sm  # type: ignore[unresolved-attribute]

    @patch("strands_compose.config.resolvers.agents.resolve_session_manager")
    def test_non_swarm_agent_with_explicit_sm_uses_per_agent_sm(
        self, mock_resolve_sm, patch_agent_init
    ):
        """Non-swarm agent with an explicit per-agent SM uses that SM, not the global one."""
        per_agent_sm = MagicMock()
        mock_resolve_sm.return_value = per_agent_sm
        sm_def = SessionManagerDef(provider="file")
        agent_def = AgentDef(session_manager=sm_def)
        global_sm = MagicMock()
        result = resolve_agents(
            {"main": agent_def},
            models={},
            mcp_clients={},
            session_manager=global_sm,
        )
        assert result["main"]._init_kwargs["session_manager"] is per_agent_sm  # type: ignore[unresolved-attribute]

    def test_non_swarm_agent_with_explicit_null_sm_opts_out(self, patch_agent_init):
        """Non-swarm agent with session_manager: ~ opts out of the global SM."""
        global_sm = MagicMock()
        agent_def = AgentDef(session_manager=None)  # explicit None -> opt-out
        result = resolve_agents(
            {"main": agent_def},
            models={},
            mcp_clients={},
            session_manager=global_sm,
        )
        assert result["main"]._init_kwargs["session_manager"] is None  # type: ignore[unresolved-attribute]


class TestResolveOrchestration:
    def test_single_agent_mode_returns_empty_dict(self):
        config = MagicMock()
        config.orchestrations = {}
        agent = MagicMock(spec=_RealAgent)
        orchestrators = resolve_orchestrations(config, {"main": agent}, {}, {}, {})
        assert orchestrators == {}

    @patch("strands_compose.config.resolvers.orchestrations.OrchestrationBuilder")
    def test_with_named_orchestrations(self, mock_builder_cls):
        config = MagicMock()
        config.orchestrations = {
            "my_swarm": SwarmOrchestrationDef(entry_name="a", agents=["a", "b"]),
        }
        agents = {"a": MagicMock(spec=_RealAgent), "b": MagicMock(spec=_RealAgent)}
        mock_swarm = MagicMock()
        mock_builder = MagicMock()
        mock_builder.build_all.return_value = {"my_swarm": mock_swarm}
        mock_builder_cls.return_value = mock_builder
        orchestrators = resolve_orchestrations(config, agents, {}, {}, {})  # type: ignore[arg-type]
        assert orchestrators == {"my_swarm": mock_swarm}
        mock_builder_cls.assert_called_once()
        mock_builder.build_all.assert_called_once()
