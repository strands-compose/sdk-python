"""Tests for config.loaders.loaders — load_session."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from strands_compose.config.loaders.loaders import load_session
from strands_compose.config.resolvers.config import ResolvedConfig, ResolvedInfra
from strands_compose.config.schema import AgentDef, AppConfig, SwarmOrchestrationDef


class TestLoadSession:
    """Unit tests for load_session() — the server-pattern session builder."""

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_returns_resolved_config(self, mock_resolve_agents, mock_resolve_orch):
        mock_agent = MagicMock()
        mock_resolve_agents.return_value = {"main": mock_agent}
        mock_resolve_orch.return_value = {}

        config = AppConfig(agents={"main": AgentDef()}, entry="main")
        infra = ResolvedInfra()

        result = load_session(config, infra)

        assert isinstance(result, ResolvedConfig)
        assert result.agents == {"main": mock_agent}
        assert result.entry is mock_agent
        assert result.mcp_lifecycle is infra.mcp_lifecycle

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_agents_receive_infra_models_and_clients(self, mock_resolve_agents, mock_resolve_orch):
        mock_resolve_agents.return_value = {"main": MagicMock()}
        mock_resolve_orch.return_value = {}

        infra = ResolvedInfra()
        infra.models = {"gpt": MagicMock()}
        infra.clients = {"pg": MagicMock()}

        config = AppConfig(agents={"main": AgentDef()}, entry="main")
        load_session(config, infra)

        call_kwargs = mock_resolve_agents.call_args[1]
        assert call_kwargs["models"] is infra.models
        assert call_kwargs["mcp_clients"] is infra.clients

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_uses_infra_session_manager_by_default(self, mock_resolve_agents, mock_resolve_orch):
        mock_resolve_agents.return_value = {"main": MagicMock()}
        mock_resolve_orch.return_value = {}

        infra = ResolvedInfra()
        infra.session_manager = MagicMock()

        config = AppConfig(agents={"main": AgentDef()}, entry="main")
        load_session(config, infra)

        call_kwargs = mock_resolve_agents.call_args[1]
        assert call_kwargs["session_manager"] is infra.session_manager

    @patch("strands_compose.config.loaders.loaders.resolve_session_manager")
    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_session_id_creates_fresh_session_manager(
        self,
        mock_resolve_agents,
        mock_resolve_orch,
        mock_resolve_sm,
    ):
        from strands_compose.config.schema import SessionManagerDef

        mock_resolve_agents.return_value = {"main": MagicMock()}
        mock_resolve_orch.return_value = {}
        fresh_sm = MagicMock()
        mock_resolve_sm.return_value = fresh_sm

        config = AppConfig(
            agents={"main": AgentDef()},
            entry="main",
            session_manager=SessionManagerDef(provider="file"),
        )
        infra = ResolvedInfra()
        infra.session_manager = MagicMock()

        load_session(config, infra, session_id="abc-123")

        mock_resolve_sm.assert_called_once()
        call_kwargs = mock_resolve_agents.call_args[1]
        assert call_kwargs["session_manager"] is fresh_sm

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_session_id_without_config_sm_uses_infra_sm(
        self, mock_resolve_agents, mock_resolve_orch
    ):
        mock_resolve_agents.return_value = {"main": MagicMock()}
        mock_resolve_orch.return_value = {}

        infra = ResolvedInfra()
        infra.session_manager = MagicMock()

        config = AppConfig(agents={"main": AgentDef()}, entry="main")
        load_session(config, infra, session_id="abc-123")

        call_kwargs = mock_resolve_agents.call_args[1]
        assert call_kwargs["session_manager"] is infra.session_manager

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_swarm_agents_excluded_from_session_manager(
        self, mock_resolve_agents, mock_resolve_orch
    ):
        mock_resolve_agents.return_value = {"a": MagicMock(), "b": MagicMock()}
        mock_resolve_orch.return_value = {}

        config = AppConfig(
            agents={"a": AgentDef(), "b": AgentDef()},
            entry="a",
            orchestrations={
                "sw": SwarmOrchestrationDef(
                    mode="swarm",
                    agents=["a", "b"],
                    entry_name="a",
                )
            },
        )
        infra = ResolvedInfra()
        load_session(config, infra)

        call_kwargs = mock_resolve_agents.call_args[1]
        assert call_kwargs["swarm_agent_names"] == {"a", "b"}

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_orchestrators_in_result(self, mock_resolve_agents, mock_resolve_orch):
        mock_agent = MagicMock()
        mock_orch = MagicMock()
        mock_resolve_agents.return_value = {"main": mock_agent}
        mock_resolve_orch.return_value = {"orch": mock_orch}

        config = AppConfig(
            agents={"main": AgentDef()},
            orchestrations={
                "orch": SwarmOrchestrationDef(mode="swarm", agents=["main"], entry_name="main")
            },
            entry="orch",
        )
        infra = ResolvedInfra()

        result = load_session(config, infra)

        assert result.orchestrators == {"orch": mock_orch}
        assert result.entry is mock_orch

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_does_not_stop_infra_on_exception(self, mock_resolve_agents, mock_resolve_orch):
        """P0-3: load_session must NOT stop shared MCP infrastructure on failure."""
        mock_resolve_agents.side_effect = RuntimeError("agent build failed")

        config = AppConfig(agents={"main": AgentDef()}, entry="main")
        infra = ResolvedInfra()
        infra.mcp_lifecycle = MagicMock()

        try:
            load_session(config, infra)
        except RuntimeError:
            pass

        # The critical assertion: infra lifecycle must NOT be stopped
        infra.mcp_lifecycle.stop.assert_not_called()
