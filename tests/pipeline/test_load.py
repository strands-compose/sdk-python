"""End-to-end load() wiring over worked YAML fixtures — the thin top layer.

Asserts the whole pipeline wires up and the entry object has the right type/
topology. Business rules are proven in resolve/; this only guards the flow.
"""

from __future__ import annotations

import pytest
from strands import Agent
from strands.multiagent import Swarm
from strands.multiagent.graph import Graph

from strands_compose.config import ResolvedConfig, load
from strands_compose.mcp import MCPLifecycle

pytestmark = pytest.mark.integration


def test_minimal_config_wires_entry_agent(fixture_path):
    resolved = load(fixture_path("minimal.yaml"))
    assert isinstance(resolved, ResolvedConfig)
    assert isinstance(resolved.entry, Agent)
    assert "greeter" in resolved.agents


def test_delegate_entry_is_the_orchestrator(fixture_path):
    resolved = load(fixture_path("delegate.yaml"))
    assert resolved.entry is resolved.orchestrators["coordinator"]
    assert {"researcher", "writer"} <= set(resolved.agents)


def test_swarm_entry_is_a_swarm(fixture_path):
    resolved = load(fixture_path("swarm.yaml"))
    assert isinstance(resolved.orchestrators["team"], Swarm)


def test_graph_entry_is_a_graph(fixture_path):
    resolved = load(fixture_path("graph.yaml"))
    assert isinstance(resolved.orchestrators["pipeline"], Graph)


def test_nested_orchestration_entry_is_outer(fixture_path):
    resolved = load(fixture_path("nested.yaml"))
    assert resolved.entry is resolved.orchestrators["full_pipeline"]


def test_multiple_sources_are_merged(fixture_path):
    resolved = load(
        [fixture_path("multi_source_base.yaml"), fixture_path("multi_source_extra.yaml")]
    )
    assert {"planner", "helper"} <= set(resolved.agents)


def test_resolved_config_carries_a_lifecycle(fixture_path):
    resolved = load(fixture_path("minimal.yaml"))
    assert isinstance(resolved.mcp_lifecycle, MCPLifecycle)
    resolved.mcp_lifecycle.stop()
