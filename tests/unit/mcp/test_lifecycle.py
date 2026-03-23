"""Tests for core.mcp.lifecycle — MCPLifecycle."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from strands_compose.mcp.lifecycle import MCPLifecycle


class TestMCPLifecycle:
    def test_add_server_and_get(self):
        lc = MCPLifecycle()
        server = MagicMock()
        lc.add_server("pg", server)
        assert lc.get_server("pg") is server

    def test_add_client_and_get(self):
        lc = MCPLifecycle()
        client = MagicMock()
        lc.add_client("c", client)
        assert lc.get_client("c") is client

    def test_duplicate_server_raises(self):
        lc = MCPLifecycle()
        lc.add_server("pg", MagicMock())
        with pytest.raises(ValueError, match="already registered"):
            lc.add_server("pg", MagicMock())

    def test_duplicate_client_raises(self):
        lc = MCPLifecycle()
        lc.add_client("c", MagicMock())
        with pytest.raises(ValueError, match="already registered"):
            lc.add_client("c", MagicMock())

    def test_get_missing_server_raises(self):
        lc = MCPLifecycle()
        with pytest.raises(KeyError):
            lc.get_server("missing")

    def test_get_missing_client_raises(self):
        lc = MCPLifecycle()
        with pytest.raises(KeyError):
            lc.get_client("missing")

    def test_start_starts_servers_not_clients(self):
        lc = MCPLifecycle()
        server = MagicMock()
        server.wait_ready.return_value = True
        client = MagicMock()

        lc.add_server("s", server)
        lc.add_client("c", client)
        lc.start()

        server.start.assert_called_once()
        server.wait_ready.assert_called_once()
        client.start.assert_not_called()
        assert lc._started

    def test_start_raises_if_server_not_ready(self):
        lc = MCPLifecycle()
        server = MagicMock()
        server.wait_ready.return_value = False
        lc.add_server("s", server)
        with pytest.raises(RuntimeError, match="did not become ready"):
            lc.start()

    def test_stop_stops_clients_then_servers(self):
        lc = MCPLifecycle()
        server = MagicMock()
        server.wait_ready.return_value = True
        client = MagicMock()

        lc.add_server("s", server)
        lc.add_client("c", client)
        lc.start()
        lc.stop()

        client.stop.assert_called_once_with(exc_type=None, exc_val=None, exc_tb=None)
        server.stop.assert_called_once()
        assert not lc._started

    def test_context_manager(self):
        lc = MCPLifecycle()
        server = MagicMock()
        server.wait_ready.return_value = True
        lc.add_server("s", server)

        with lc:
            assert lc._started
        assert not lc._started

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        lc = MCPLifecycle()
        server = MagicMock()
        server.wait_ready.return_value = True
        lc.add_server("s", server)

        async with lc:
            assert lc._started
            server.start.assert_called_once()
        assert not lc._started
        server.stop.assert_called_once()

    def test_stop_without_start_is_noop(self):
        lc = MCPLifecycle()
        lc.add_server("s", MagicMock())
        lc.stop()  # should not raise
        assert not lc._started

    def test_start_idempotent(self):
        lc = MCPLifecycle()
        server = MagicMock()
        server.wait_ready.return_value = True
        lc.add_server("s", server)
        lc.start()
        lc.start()  # second call should be no-op
        server.start.assert_called_once()

    def test_stop_suppresses_client_errors(self):
        lc = MCPLifecycle()
        server = MagicMock()
        server.wait_ready.return_value = True
        client = MagicMock()
        client.stop.side_effect = RuntimeError("connection lost")
        lc.add_server("s", server)
        lc.add_client("c", client)
        lc.start()
        lc.stop()  # should not raise
        assert not lc._started

    def test_stop_suppresses_server_errors(self):
        lc = MCPLifecycle()
        server = MagicMock()
        server.wait_ready.return_value = True
        server.stop.side_effect = RuntimeError("stop failed")
        lc.add_server("s", server)
        lc.start()
        lc.stop()  # should not raise
        assert not lc._started

    def test_servers_and_clients_properties(self):
        lc = MCPLifecycle()
        server = MagicMock()
        client = MagicMock()
        lc.add_server("s", server)
        lc.add_client("c", client)
        assert lc.servers == {"s": server}
        assert lc.clients == {"c": client}
