"""Tests for core.mcp.client — create_mcp_client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from strands_compose.mcp.client import (
    _detect_transport,
    _transport_for_http,
    create_mcp_client,
)


class TestCreateMcpClient:
    def test_no_connection_params_raises(self):
        with pytest.raises(ValueError, match="Exactly one"):
            create_mcp_client()

    def test_multiple_params_raises(self):
        with pytest.raises(ValueError, match="Exactly one"):
            create_mcp_client(url="http://x", command=["python"])

    @patch("strands_compose.mcp.client._make_strands_client")
    @patch("strands_compose.mcp.client._transport_for_http")
    def test_create_with_server(self, mock_transport, mock_make):
        server = MagicMock()
        mock_transport.return_value = "transport-callable"
        mock_make.return_value = "client"
        result = create_mcp_client(server=server)
        mock_transport.assert_called_once_with(server.url, "streamable-http", {}, allow_stdio=False)
        mock_make.assert_called_once_with(transport_callable="transport-callable")
        assert result == "client"

    @patch("strands_compose.mcp.client._make_strands_client")
    @patch("strands_compose.mcp.client._transport_for_http")
    def test_create_with_url(self, mock_transport, mock_make):
        mock_transport.return_value = "transport-callable"
        mock_make.return_value = "client"
        result = create_mcp_client(url="http://localhost:8000/mcp")
        mock_transport.assert_called_once_with(
            "http://localhost:8000/mcp", "streamable-http", {}, allow_stdio=True
        )
        mock_make.assert_called_once_with(transport_callable="transport-callable")
        assert result == "client"

    @patch("strands_compose.mcp.client._make_strands_client")
    @patch("strands_compose.mcp.client.stdio_transport")
    def test_create_with_command(self, mock_stdio, mock_make):
        mock_stdio.return_value = "transport-callable"
        mock_make.return_value = "client"
        result = create_mcp_client(command=["python", "-m", "server"])
        mock_stdio.assert_called_once_with(["python", "-m", "server"])
        mock_make.assert_called_once_with(transport_callable="transport-callable")
        assert result == "client"

    @patch("strands_compose.mcp.client._make_strands_client")
    @patch("strands_compose.mcp.client._transport_for_http")
    def test_create_forwards_extra_kwargs(self, mock_transport, mock_make):
        mock_transport.return_value = "t"
        mock_make.return_value = "client"
        create_mcp_client(url="http://x", startup_timeout=30)
        mock_make.assert_called_once_with(transport_callable="t", startup_timeout=30)

    @patch("strands_compose.mcp.client._make_strands_client")
    @patch("strands_compose.mcp.client._transport_for_http")
    def test_create_with_transport_options(self, mock_transport, mock_make):
        server = MagicMock()
        mock_transport.return_value = "t"
        mock_make.return_value = "client"
        opts = {"headers": {"Authorization": "Bearer tok"}, "terminate_on_close": False}
        create_mcp_client(server=server, transport_options=opts)
        mock_transport.assert_called_once_with(
            server.url, "streamable-http", opts, allow_stdio=False
        )

    @patch("strands_compose.mcp.client._make_strands_client")
    @patch("strands_compose.mcp.client.stdio_transport")
    def test_create_command_forwards_transport_options(self, mock_stdio, mock_make):
        mock_stdio.return_value = "t"
        mock_make.return_value = "client"
        create_mcp_client(command=["node", "server.js"], transport_options={"cwd": "/tmp"})  # nosec B108
        mock_stdio.assert_called_once_with(["node", "server.js"], cwd="/tmp")  # nosec B108


class TestMakeStrandsClient:
    @patch("strands.tools.mcp.MCPClient")
    def test_make_strands_client(self, mock_cls):
        from strands_compose.mcp.client import _make_strands_client

        mock_cls.return_value = "instance"
        result = _make_strands_client(transport_callable="tc", startup_timeout=10)
        mock_cls.assert_called_once_with(transport_callable="tc", startup_timeout=10)
        assert result == "instance"


class TestDetectTransport:
    def test_sse_detected(self):
        assert _detect_transport("http://localhost/sse") == "sse"

    def test_default_streamable_http(self):
        assert _detect_transport("http://localhost/mcp") == "streamable-http"


class TestTransportForHttp:
    @patch("strands_compose.mcp.client.streamable_http_transport")
    def test_streamable_http_default(self, mock_transport):
        mock_transport.return_value = "transport"
        result = _transport_for_http("http://localhost:8000/mcp", None)
        mock_transport.assert_called_once_with("http://localhost:8000/mcp")
        assert result == "transport"

    @patch("strands_compose.mcp.client.streamable_http_transport")
    def test_streamable_http_explicit(self, mock_transport):
        mock_transport.return_value = "transport"
        result = _transport_for_http("http://localhost:8000/mcp", "streamable-http")
        mock_transport.assert_called_once_with("http://localhost:8000/mcp")
        assert result == "transport"

    @patch("strands_compose.mcp.client.sse_transport")
    def test_sse_explicit(self, mock_transport):
        mock_transport.return_value = "transport"
        result = _transport_for_http("http://localhost:8000/sse", "sse")
        mock_transport.assert_called_once_with("http://localhost:8000/sse")
        assert result == "transport"

    @patch("strands_compose.mcp.client.streamable_http_transport")
    def test_auto_detect_streamable_http(self, mock_transport):
        mock_transport.return_value = "transport"
        result = _transport_for_http("http://localhost:8000/mcp", None)
        mock_transport.assert_called_once_with("http://localhost:8000/mcp")
        assert result == "transport"

    @patch("strands_compose.mcp.client.sse_transport")
    def test_auto_detect_sse(self, mock_transport):
        mock_transport.return_value = "transport"
        result = _transport_for_http("http://localhost:8000/sse", None)
        mock_transport.assert_called_once_with("http://localhost:8000/sse")
        assert result == "transport"

    @patch("strands_compose.mcp.client.streamable_http_transport")
    def test_forwards_transport_options(self, mock_transport):
        mock_transport.return_value = "transport"
        opts = {"terminate_on_close": False}
        result = _transport_for_http("http://localhost:8000/mcp", "streamable-http", opts)
        mock_transport.assert_called_once_with(
            "http://localhost:8000/mcp", terminate_on_close=False
        )
        assert result == "transport"

    @patch("strands_compose.mcp.client.sse_transport")
    def test_forwards_sse_transport_options(self, mock_transport):
        mock_transport.return_value = "transport"
        opts = {"timeout": 30, "sse_read_timeout": 600}
        result = _transport_for_http("http://localhost:8000/sse", "sse", opts)
        mock_transport.assert_called_once_with(
            "http://localhost:8000/sse", timeout=30, sse_read_timeout=600
        )
        assert result == "transport"

    def test_stdio_raises_when_not_allowed(self):
        with pytest.raises(ValueError, match="not supported"):
            _transport_for_http("http://x", "stdio", allow_stdio=False)

    def test_stdio_raises_as_unsupported_http_transport(self):
        with pytest.raises(ValueError, match="requires.*sse.*streamable-http"):
            _transport_for_http("http://x", "stdio", allow_stdio=True)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="requires.*sse.*streamable-http"):
            _transport_for_http("http://x", "grpc")
