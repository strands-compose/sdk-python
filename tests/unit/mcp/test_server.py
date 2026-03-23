"""Tests for core.mcp.server — MCPServer abstract base class."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from strands_compose.mcp.server import MCPServer, create_mcp_server


class ConcreteMCPServer(MCPServer):
    def _register_tools(self, mcp):
        pass


class TestMCPServer:
    def test_url_property(self):
        s = ConcreteMCPServer(name="test", host="127.0.0.1", port=9000)
        assert s.url == "http://127.0.0.1:9000/mcp"

    def test_not_running_initially(self):
        s = ConcreteMCPServer(name="test")
        assert s.is_running is False

    def test_stop_clears_state(self):
        s = ConcreteMCPServer(name="test")
        s._mcp = MagicMock()
        s._thread = MagicMock()
        s._uvicorn_server = MagicMock()
        s.stop()
        assert s._mcp is None
        assert s._thread is None
        assert s._uvicorn_server is None

    @patch("mcp.server.fastmcp.FastMCP")
    def test_create_server_caches(self, mock_cls):
        mock_cls.return_value = MagicMock()
        s = ConcreteMCPServer(name="test")
        first = s.create_server()
        second = s.create_server()
        assert first is second

    def test_start_sets_thread_and_uvicorn_server(self):
        """start() should create both a thread and a uvicorn.Server for HTTP transports."""
        s = ConcreteMCPServer(name="test", port=19999)
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = MagicMock()

        with (
            patch.object(s, "create_server", return_value=mock_mcp),
            patch("uvicorn.Config") as mock_config_cls,
            patch("uvicorn.Server") as mock_server_cls,
        ):
            mock_config_cls.return_value = MagicMock()
            mock_server = MagicMock()
            mock_server_cls.return_value = mock_server

            s.start()
            assert s._thread is not None
            assert s._uvicorn_server is mock_server
            s.stop()

    def test_start_idempotent_when_running(self):
        s = ConcreteMCPServer(name="test")
        s._thread = MagicMock()
        s._thread.is_alive.return_value = True
        s.start()  # should not create a new thread

    # -- stop() graceful shutdown ----------------------------------- #

    def test_stop_sets_should_exit_on_uvicorn_server(self):
        """stop() should signal should_exit on the uvicorn.Server."""
        s = ConcreteMCPServer(name="test")
        mock_uv = MagicMock()
        mock_uv.should_exit = False
        mock_uv.force_exit = False
        s._uvicorn_server = mock_uv

        mock_thread = MagicMock()
        # Thread is alive initially, exits after join, final check confirms dead
        mock_thread.is_alive.side_effect = [True, False, False]
        s._thread = mock_thread

        s.stop()
        assert mock_uv.should_exit is True
        assert mock_uv.force_exit is False  # should not escalate

    def test_stop_escalates_to_force_exit(self):
        """stop() should set force_exit if the thread is still alive after STOP_TIMEOUT."""
        s = ConcreteMCPServer(name="test")
        mock_uv = MagicMock()
        mock_uv.should_exit = False
        mock_uv.force_exit = False
        s._uvicorn_server = mock_uv

        mock_thread = MagicMock()
        # Thread is alive during the first join, then exits after force_exit
        mock_thread.is_alive.side_effect = [True, True, False]
        s._thread = mock_thread

        s.stop()
        assert mock_uv.should_exit is True
        assert mock_uv.force_exit is True
        # join called twice: once for graceful, once for force
        assert mock_thread.join.call_count == 2

    def test_stop_warns_if_thread_wont_die(self):
        """stop() should log a warning if the thread refuses to exit."""
        s = ConcreteMCPServer(name="test")
        mock_uv = MagicMock()
        s._uvicorn_server = mock_uv

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True  # never exits
        s._thread = mock_thread

        with patch("strands_compose.mcp.server.logger") as mock_logger:
            s.stop()
            mock_logger.warning.assert_called_once()
            assert "did not stop" in mock_logger.warning.call_args[0][0]

    # -- _get_asgi_app ---------------------------------------------- #

    def test_get_asgi_app_streamable_http(self):
        s = ConcreteMCPServer(name="test", transport="streamable-http")
        mock_mcp = MagicMock()
        mock_mcp.streamable_http_app.return_value = "streamable_app"
        assert s._get_asgi_app(mock_mcp) == "streamable_app"

    def test_get_asgi_app_sse(self):
        s = ConcreteMCPServer(name="test", transport="sse")
        mock_mcp = MagicMock()
        mock_mcp.sse_app.return_value = "sse_app"
        assert s._get_asgi_app(mock_mcp) == "sse_app"

    def test_get_asgi_app_raises_for_unsupported_transport(self):
        """_get_asgi_app should raise ValueError for unsupported transports like stdio."""
        s = ConcreteMCPServer(name="test")
        s.transport = "stdio"  # force invalid value
        mock_mcp = MagicMock()
        with pytest.raises(ValueError, match="Unsupported server transport.*stdio"):
            s._get_asgi_app(mock_mcp)

    # -- class-level timeout attributes ----------------------------- #

    def test_default_timeouts(self):
        s = ConcreteMCPServer(name="test")
        assert s.STOP_TIMEOUT == 5
        assert s.STOP_FORCE_TIMEOUT == 2


class TestCreateMcpServer:
    """Tests for the create_mcp_server factory function."""

    def test_returns_mcp_server_instance(self):
        server = create_mcp_server(name="test", tools=[])
        assert isinstance(server, MCPServer)

    def test_name_and_port_forwarded(self):
        server = create_mcp_server(name="my-srv", tools=[], port=9999, host="0.0.0.0")
        assert server.name == "my-srv"
        assert server.port == 9999
        assert server.host == "0.0.0.0"

    @patch("mcp.server.fastmcp.FastMCP")
    def test_tools_registered_on_create_server(self, mock_cls):
        mock_mcp = MagicMock()
        mock_cls.return_value = mock_mcp

        def tool_a() -> str:
            return "a"

        def tool_b(x: int) -> int:
            return x

        server = create_mcp_server(name="test", tools=[tool_a, tool_b])
        server.create_server()

        # Each tool should be registered via mcp.tool()(fn)
        assert mock_mcp.tool.return_value.call_count == 2
        calls = mock_mcp.tool.return_value.call_args_list
        assert calls[0].args[0] is tool_a
        assert calls[1].args[0] is tool_b

    @patch("mcp.server.fastmcp.FastMCP")
    def test_empty_tools_list(self, mock_cls):
        mock_mcp = MagicMock()
        mock_cls.return_value = mock_mcp

        server = create_mcp_server(name="empty", tools=[])
        server.create_server()

        mock_mcp.tool.return_value.assert_not_called()

    def test_server_params_forwarded(self):
        params = {"custom_key": "custom_val"}
        server = create_mcp_server(name="test", tools=[], server_params=params)
        assert server.server_params == params

    def test_url_property(self):
        server = create_mcp_server(name="test", tools=[], host="localhost", port=5555)
        assert server.url == "http://localhost:5555/mcp"
