"""MCP lifecycle — ordering and idempotency observed via owned fakes.

Asserts the contract through the fake's recorded calls, never private flags.
"""

from __future__ import annotations

import threading

import pytest

from strands_compose.mcp.lifecycle import MCPLifecycle
from tests.fakes import FakeMCPClient, FakeMCPServer


def test_start_starts_server_and_probes_readiness():
    lc = MCPLifecycle()
    server = FakeMCPServer()
    lc.add_server("s", server)

    lc.start()

    assert server.calls == ["start", "wait_ready"]


def test_start_is_idempotent():
    lc = MCPLifecycle()
    server = FakeMCPServer()
    lc.add_server("s", server)

    lc.start()
    lc.start()

    assert server.calls.count("start") == 1


def test_stop_stops_clients_before_servers():
    lc = MCPLifecycle()
    order: list[str] = []
    server = FakeMCPServer(record=order, label="server")
    client = FakeMCPClient(record=order, label="client")
    lc.add_server("s", server)
    lc.add_client("c", client)  # ty: ignore[invalid-argument-type]

    lc.start()
    lc.stop()

    assert order == ["client", "server"]


def test_stop_before_start_is_a_noop():
    lc = MCPLifecycle()
    server = FakeMCPServer()
    lc.add_server("s", server)
    lc.stop()
    assert "stop" not in server.calls


def test_duplicate_server_registration_raises():
    lc = MCPLifecycle()
    lc.add_server("s", FakeMCPServer())
    with pytest.raises(ValueError):
        lc.add_server("s", FakeMCPServer())


def test_unready_server_fails_start():
    lc = MCPLifecycle(server_ready_timeout=0.01)
    lc.add_server("s", FakeMCPServer(ready=False))
    with pytest.raises(RuntimeError):
        lc.start()


def test_get_missing_client_raises_key_error():
    lc = MCPLifecycle()
    with pytest.raises(KeyError):
        lc.get_client("nope")


def test_concurrent_start_starts_server_once():
    lc = MCPLifecycle()
    server = FakeMCPServer()
    lc.add_server("s", server)

    threads = [threading.Thread(target=lc.start) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert server.calls.count("start") == 1
