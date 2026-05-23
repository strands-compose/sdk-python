"""Tests for config.loaders.loaders — load_session."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from strands_compose.config.loaders.loaders import load_session
from strands_compose.config.resolvers.config import ResolvedConfig, ResolvedInfra
from strands_compose.config.schema import (
    AgentDef,
    AppConfig,
    GraphEdgeDef,
    GraphOrchestrationDef,
    SessionManagerDef,
    SwarmOrchestrationDef,
)


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
    def test_global_session_manager_def_forwarded(self, mock_agents, mock_orch):
        mock_agents.return_value = {"main": MagicMock()}
        mock_orch.return_value = {}
        sm_def = SessionManagerDef(provider="file")
        config = AppConfig(agents={"main": AgentDef()}, entry="main", session_manager=sm_def)
        load_session(config, ResolvedInfra())
        assert mock_agents.call_args.kwargs["global_session_manager_def"] is sm_def
        assert mock_orch.call_args.kwargs["global_session_manager_def"] is sm_def

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_no_global_session_manager_def_is_none(self, mock_agents, mock_orch):
        mock_agents.return_value = {"main": MagicMock()}
        mock_orch.return_value = {}
        config = AppConfig(agents={"main": AgentDef()}, entry="main")
        load_session(config, ResolvedInfra())
        assert mock_agents.call_args.kwargs["global_session_manager_def"] is None
        assert mock_agents.call_args.kwargs["session_id"] is None

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_explicit_session_id_threaded(self, mock_agents, mock_orch):
        mock_agents.return_value = {"main": MagicMock()}
        mock_orch.return_value = {}
        sm_def = SessionManagerDef(provider="file")
        config = AppConfig(agents={"main": AgentDef()}, entry="main", session_manager=sm_def)
        load_session(config, ResolvedInfra(), session_id="abc-123")
        assert mock_agents.call_args.kwargs["session_id"] == "abc-123"
        assert mock_orch.call_args.kwargs["session_id"] == "abc-123"

    @patch("strands_compose.config.loaders.loaders.uuid")
    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_cli_mode_synthesises_session_id_when_global_sm_set(
        self, mock_agents, mock_orch, mock_uuid
    ):
        mock_agents.return_value = {"main": MagicMock()}
        mock_orch.return_value = {}
        mock_uuid.uuid4.return_value = "deadbeef"
        sm_def = SessionManagerDef(provider="file")
        config = AppConfig(agents={"main": AgentDef()}, entry="main", session_manager=sm_def)
        load_session(config, ResolvedInfra())
        assert mock_agents.call_args.kwargs["session_id"] == "deadbeef"
        assert mock_orch.call_args.kwargs["session_id"] == "deadbeef"

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_cli_mode_uses_yaml_session_id_when_present(self, mock_agents, mock_orch):
        mock_agents.return_value = {"main": MagicMock()}
        mock_orch.return_value = {}
        sm_def = SessionManagerDef(provider="file", params={"session_id": "from-yaml"})
        config = AppConfig(agents={"main": AgentDef()}, entry="main", session_manager=sm_def)
        load_session(config, ResolvedInfra())
        assert mock_agents.call_args.kwargs["session_id"] == "from-yaml"

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_cli_mode_no_global_sm_keeps_session_id_none(self, mock_agents, mock_orch):
        mock_agents.return_value = {"main": MagicMock()}
        mock_orch.return_value = {}
        config = AppConfig(agents={"main": AgentDef()}, entry="main")
        load_session(config, ResolvedInfra())
        assert mock_agents.call_args.kwargs["session_id"] is None

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
        assert call_kwargs["orchestration_agent_names"] == {"a", "b"}

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_graph_agents_excluded_from_session_manager(
        self, mock_resolve_agents, mock_resolve_orch
    ):
        mock_resolve_agents.return_value = {"a": MagicMock(), "b": MagicMock()}
        mock_resolve_orch.return_value = {}

        config = AppConfig(
            agents={"a": AgentDef(), "b": AgentDef()},
            entry="a",
            orchestrations={
                "gr": GraphOrchestrationDef(
                    mode="graph",
                    entry_name="a",
                    edges=[GraphEdgeDef(**{"from": "a", "to": "b"})],
                )
            },
        )
        infra = ResolvedInfra()
        load_session(config, infra)

        call_kwargs = mock_resolve_agents.call_args[1]
        assert call_kwargs["orchestration_agent_names"] == {"a", "b"}

    @patch("strands_compose.config.loaders.loaders.resolve_orchestrations")
    @patch("strands_compose.config.loaders.loaders.resolve_agents")
    def test_swarm_and_graph_agents_combined_in_orchestration_agent_names(
        self, mock_resolve_agents, mock_resolve_orch
    ):
        mock_resolve_agents.return_value = {"a": MagicMock(), "b": MagicMock(), "c": MagicMock()}
        mock_resolve_orch.return_value = {}

        config = AppConfig(
            agents={"a": AgentDef(), "b": AgentDef(), "c": AgentDef()},
            entry="a",
            orchestrations={
                "sw": SwarmOrchestrationDef(mode="swarm", agents=["a", "b"], entry_name="a"),
                "gr": GraphOrchestrationDef(
                    mode="graph",
                    entry_name="b",
                    edges=[GraphEdgeDef(**{"from": "b", "to": "c"})],
                ),
            },
        )
        infra = ResolvedInfra()
        load_session(config, infra)

        call_kwargs = mock_resolve_agents.call_args[1]
        assert call_kwargs["orchestration_agent_names"] == {"a", "b", "c"}

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
