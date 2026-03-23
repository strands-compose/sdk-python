"""Tests for core.config.resolvers.config — resolve_infra, ResolvedConfig, and ResolvedInfra."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from strands_compose.config.resolvers.config import (
    ResolvedConfig,
    ResolvedInfra,
    resolve_infra,
)
from strands_compose.config.schema import (
    AgentDef,
    AppConfig,
    MCPClientDef,
    MCPServerDef,
    ModelDef,
    SessionManagerDef,
)


class TestResolvedConfig:
    def test_defaults(self):
        mock_entry = MagicMock()
        rc = ResolvedConfig(entry=mock_entry)
        assert rc.agents == {}
        assert rc.entry is mock_entry
        assert rc.mcp_lifecycle is not None


class TestResolvedInfra:
    def test_defaults(self):
        infra = ResolvedInfra()
        assert infra.models == {}
        assert infra.clients == {}
        assert infra.session_manager is None
        assert infra.mcp_lifecycle is not None


class TestResolveAll:
    """resolve_infra() is pure — creates objects without starting anything."""

    def test_minimal_config(self):
        config = AppConfig(agents={"main": AgentDef()}, entry="main")
        result = resolve_infra(config)
        assert isinstance(result, ResolvedInfra)
        assert result.models == {}
        assert result.clients == {}
        assert result.session_manager is None
        assert result.mcp_lifecycle._started is False

    @patch("strands_compose.config.resolvers.config.resolve_model")
    def test_models_resolved(self, mock_resolve_model):
        mock_model = MagicMock()
        mock_resolve_model.return_value = mock_model
        config = AppConfig(
            models={"gpt": ModelDef(provider="bedrock", model_id="nova")},
            agents={"main": AgentDef()},
            entry="main",
        )
        result = resolve_infra(config)
        mock_resolve_model.assert_called_once()
        assert result.models == {"gpt": mock_model}

    @patch("strands_compose.config.resolvers.config.resolve_mcp_server")
    def test_mcp_servers_registered_not_started(self, mock_resolve_server):
        mock_server = MagicMock()
        mock_resolve_server.return_value = mock_server
        config = AppConfig(
            mcp_servers={"pg": MCPServerDef(type="my.module:PgServer")},
            agents={"main": AgentDef()},
            entry="main",
        )
        result = resolve_infra(config)
        mock_resolve_server.assert_called_once()
        # Server registered in lifecycle but NOT started
        assert "pg" in result.mcp_lifecycle.servers
        mock_server.start.assert_not_called()
        assert result.mcp_lifecycle._started is False

    @patch("strands_compose.config.resolvers.config.resolve_mcp_client")
    @patch("strands_compose.config.resolvers.config.resolve_mcp_server")
    def test_mcp_clients_resolved(self, mock_resolve_server, mock_resolve_client):
        mock_server = MagicMock()
        mock_resolve_server.return_value = mock_server
        mock_client = MagicMock()
        mock_resolve_client.return_value = mock_client
        config = AppConfig(
            mcp_servers={"pg": MCPServerDef(type="my.module:PgServer")},
            mcp_clients={"pg-client": MCPClientDef(server="pg")},
            agents={"main": AgentDef()},
            entry="main",
        )
        result = resolve_infra(config)
        mock_resolve_client.assert_called_once()
        assert result.clients == {"pg-client": mock_client}
        # Both registered in lifecycle
        assert "pg" in result.mcp_lifecycle.servers
        assert "pg-client" in result.mcp_lifecycle.clients

    @patch("strands_compose.config.resolvers.config.resolve_session_manager")
    def test_session_manager_resolved(self, mock_resolve_sm):
        mock_sm = MagicMock()
        mock_resolve_sm.return_value = mock_sm
        config = AppConfig(
            session_manager=SessionManagerDef(provider="file"),
            agents={"main": AgentDef()},
            entry="main",
        )
        result = resolve_infra(config)
        mock_resolve_sm.assert_called_once()
        assert result.session_manager is mock_sm

    def test_no_session_manager(self):
        config = AppConfig(agents={"main": AgentDef()}, entry="main")
        result = resolve_infra(config)
        assert result.session_manager is None

    @patch("strands_compose.config.resolvers.config.resolve_model")
    @patch("strands_compose.config.resolvers.config.resolve_mcp_client")
    @patch("strands_compose.config.resolvers.config.resolve_mcp_server")
    @patch("strands_compose.config.resolvers.config.resolve_session_manager")
    def test_full_infra_pipeline(self, mock_sm, mock_server, mock_client, mock_model):
        mock_model.return_value = MagicMock()
        mock_server.return_value = MagicMock()
        mock_client.return_value = MagicMock()
        mock_sm.return_value = MagicMock()

        config = AppConfig(
            models={"gpt": ModelDef(provider="bedrock", model_id="nova")},
            mcp_servers={"pg": MCPServerDef(type="my.module:PgServer")},
            mcp_clients={"pg-client": MCPClientDef(server="pg")},
            session_manager=SessionManagerDef(provider="file"),
            agents={"main": AgentDef(), "helper": AgentDef()},
            entry="main",
        )
        result = resolve_infra(config)
        assert isinstance(result, ResolvedInfra)
        assert "gpt" in result.models
        assert "pg-client" in result.clients
        assert result.session_manager is not None
        # Lifecycle assembled but NOT started
        assert "pg" in result.mcp_lifecycle.servers
        assert "pg-client" in result.mcp_lifecycle.clients
        assert result.mcp_lifecycle._started is False
