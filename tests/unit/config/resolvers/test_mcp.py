"""Tests for core.config.resolvers.mcp — resolve_mcp_client, resolve_mcp_server, resolve_tools."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from strands_compose.config.resolvers.mcp import (
    resolve_mcp_client,
    resolve_mcp_server,
    resolve_tools,
)
from strands_compose.config.schema import MCPClientDef, MCPServerDef


class TestResolveMcpClient:
    @patch("strands_compose.config.resolvers.mcp.create_mcp_client")
    def test_url_client(self, mock_create):
        client_def = MCPClientDef(url="http://localhost:8000")
        resolve_mcp_client(client_def, {}, name="test")
        mock_create.assert_called_once_with(
            server=None, url="http://localhost:8000", command=None, transport_options=None
        )

    def test_missing_server_ref_raises(self):
        client_def = MCPClientDef(server="missing")
        with pytest.raises(ValueError, match="not defined"):
            resolve_mcp_client(client_def, {}, name="test")

    @patch("strands_compose.config.resolvers.mcp.create_mcp_client")
    def test_server_ref_resolved(self, mock_create):
        server = MagicMock()
        client_def = MCPClientDef(server="pg")
        resolve_mcp_client(client_def, {"pg": server}, name="test")
        mock_create.assert_called_once_with(
            server=server, url=None, command=None, transport_options=None
        )

    @patch("strands_compose.config.resolvers.mcp.create_mcp_client")
    def test_command_client(self, mock_create):
        client_def = MCPClientDef(command=["python", "-m", "my_server"])
        resolve_mcp_client(client_def, {}, name="test")
        mock_create.assert_called_once_with(
            server=None, url=None, command=["python", "-m", "my_server"], transport_options=None
        )

    @patch("strands_compose.config.resolvers.mcp.create_mcp_client")
    def test_transport_passed_when_set(self, mock_create):
        client_def = MCPClientDef(url="http://localhost:8000", transport="streamable_http")
        resolve_mcp_client(client_def, {}, name="test")
        mock_create.assert_called_once_with(
            server=None,
            url="http://localhost:8000",
            command=None,
            transport="streamable_http",
            transport_options=None,
        )

    @patch("strands_compose.config.resolvers.mcp.create_mcp_client")
    def test_extra_params_forwarded(self, mock_create):
        client_def = MCPClientDef(url="http://localhost:8000", params={"timeout": 30})
        resolve_mcp_client(client_def, {}, name="test")
        mock_create.assert_called_once_with(
            server=None,
            url="http://localhost:8000",
            command=None,
            transport_options=None,
            timeout=30,
        )

    def test_missing_server_ref_shows_available(self):
        servers = {"alpha": MagicMock(), "beta": MagicMock()}
        client_def = MCPClientDef(server="missing")
        with pytest.raises(ValueError, match="alpha, beta"):
            resolve_mcp_client(client_def, servers, name="test")  # type: ignore[arg-type]

    @patch("strands_compose.config.resolvers.mcp.create_mcp_client")
    def test_tool_filters_passthrough(self, mock_create):
        """tool_filters with allowed/rejected keys passes through to MCPClient."""
        filters = {"allowed": ["read_file", "search"], "rejected": ["delete_file"]}
        client_def = MCPClientDef(url="http://localhost:8000", params={"tool_filters": filters})
        resolve_mcp_client(client_def, {}, name="test")
        mock_create.assert_called_once_with(
            server=None,
            url="http://localhost:8000",
            command=None,
            transport_options=None,
            tool_filters=filters,
        )


class TestResolveMcpServer:
    @patch("strands_compose.config.resolvers.mcp.load_object")
    def test_valid_server(self, mock_import):
        from strands_compose.mcp.server import MCPServer

        mock_server = MagicMock(spec=MCPServer)
        mock_import.return_value = MagicMock(return_value=mock_server)
        server_def = MCPServerDef(type="my.module:MyServer", params={"port": 8080})
        result = resolve_mcp_server(server_def, name="pg")
        assert result is mock_server

    @patch("strands_compose.config.resolvers.mcp.load_object")
    def test_non_mcp_server_raises_type_error(self, mock_import):
        mock_import.return_value = MagicMock(return_value="not_a_server")
        server_def = MCPServerDef(type="my.module:BadFactory")
        with pytest.raises(TypeError, match="expected MCPServer subclass"):
            resolve_mcp_server(server_def, name="bad")


class TestResolveTools:
    @patch("strands_compose.config.resolvers.mcp.resolve_tool_specs")
    def test_delegates_to_resolve_tool_specs(self, mock_resolve):
        mock_resolve.return_value = ["tool1", "tool2"]
        result = resolve_tools(["spec1", "spec2"])
        mock_resolve.assert_called_once_with(["spec1", "spec2"])
        assert result == ["tool1", "tool2"]
