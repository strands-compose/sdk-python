"""Cross-reference validation — every model/mcp/node reference must resolve.

Each broken reference raises ``UnresolvedReferenceError`` naming the bad id.
"""

from __future__ import annotations

import pytest

from strands_compose.config.loaders.validators import validate_references
from strands_compose.config.schema import AppConfig, MCPClientDef, MCPServerDef
from strands_compose.exceptions import UnresolvedReferenceError
from tests.factories import (
    agent_def,
    app_config,
    delegate_orchestration,
    graph_orchestration,
    model_def,
    swarm_orchestration,
)


def test_valid_references_pass():
    config = app_config(
        models={"fast": model_def()},
        agents={"a": agent_def(model="fast")},
        entry="a",
    )
    validate_references(config)  # does not raise


def test_missing_model_reference_raises():
    config = app_config(agents={"a": agent_def(model="ghost")}, entry="a")
    with pytest.raises(UnresolvedReferenceError, match="ghost"):
        validate_references(config)


def test_missing_mcp_client_reference_raises():
    config = app_config(agents={"a": agent_def(mcp=["nope"])}, entry="a")
    with pytest.raises(UnresolvedReferenceError, match="nope"):
        validate_references(config)


def test_missing_mcp_server_reference_raises():
    config = AppConfig(
        agents={"a": agent_def()},
        mcp_clients={"c": MCPClientDef(server="phantom")},
        entry="a",
    )
    with pytest.raises(UnresolvedReferenceError, match="phantom"):
        validate_references(config)


def test_mcp_server_reference_resolves_when_present():
    config = AppConfig(
        agents={"a": agent_def()},
        mcp_servers={"srv": MCPServerDef(type="mod:make")},
        mcp_clients={"c": MCPClientDef(server="srv")},
        entry="a",
    )
    validate_references(config)  # does not raise


def test_delegate_target_must_exist():
    config = AppConfig(
        agents={"a": agent_def()},
        orchestrations={"o": delegate_orchestration("a", {"ghost": "d"})},
        entry="o",
    )
    with pytest.raises(UnresolvedReferenceError, match="ghost"):
        validate_references(config)


def test_delegate_to_self_is_rejected():
    config = AppConfig(
        agents={"a": agent_def()},
        orchestrations={"o": delegate_orchestration("a", {"a": "d"})},
        entry="o",
    )
    with pytest.raises(UnresolvedReferenceError):
        validate_references(config)


def test_swarm_agent_must_exist():
    config = AppConfig(
        agents={"a": agent_def()},
        orchestrations={"o": swarm_orchestration("a", ["a", "missing"])},
        entry="o",
    )
    with pytest.raises(UnresolvedReferenceError, match="missing"):
        validate_references(config)


def test_graph_edge_endpoints_must_exist():
    config = AppConfig(
        agents={"a": agent_def(), "b": agent_def()},
        orchestrations={"o": graph_orchestration("a", [("a", "nowhere")])},
        entry="o",
    )
    with pytest.raises(UnresolvedReferenceError, match="nowhere"):
        validate_references(config)
