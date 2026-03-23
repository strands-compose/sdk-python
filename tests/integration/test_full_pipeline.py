"""Integration tests for load() → ResolvedConfig full pipeline."""

from __future__ import annotations

import pytest
from strands import Agent

from strands_compose.config import ResolvedConfig, load
from strands_compose.mcp import MCPLifecycle
from strands_compose.wire import EventQueue


@pytest.mark.integration
class TestLoadMinimalPipeline:
    """Full load() pipeline with the minimal fixture (single agent, no model)."""

    def test_load_returns_resolved_config(self, fixture_path):
        resolved = load(fixture_path("minimal.yaml"))
        assert isinstance(resolved, ResolvedConfig)

    def test_entry_is_agent(self, fixture_path):
        resolved = load(fixture_path("minimal.yaml"))
        assert isinstance(resolved.entry, Agent)

    def test_agents_populated(self, fixture_path):
        resolved = load(fixture_path("minimal.yaml"))
        assert "greeter" in resolved.agents
        assert isinstance(resolved.agents["greeter"], Agent)

    def test_wire_event_queue_returns_queue(self, fixture_path):
        resolved = load(fixture_path("minimal.yaml"))
        eq = resolved.wire_event_queue()
        assert isinstance(eq, EventQueue)

    def test_mcp_lifecycle_idempotent(self, fixture_path):
        resolved = load(fixture_path("minimal.yaml"))
        assert isinstance(resolved.mcp_lifecycle, MCPLifecycle)
        # start() is idempotent — already called by load()
        resolved.mcp_lifecycle.start()
        resolved.mcp_lifecycle.stop()


@pytest.mark.integration
class TestLoadDelegatePipeline:
    """Full load() pipeline with delegate orchestration."""

    def test_delegate_orchestration_wiring(self, fixture_path):
        resolved = load(fixture_path("multi_agent_delegate.yaml"))
        assert isinstance(resolved, ResolvedConfig)
        assert "coordinator" in resolved.orchestrators
        assert "researcher" in resolved.agents
        assert "writer" in resolved.agents
        assert resolved.entry is resolved.orchestrators["coordinator"]


@pytest.mark.integration
class TestLoadSwarmPipeline:
    """Full load() pipeline with swarm orchestration."""

    def test_swarm_orchestration_wiring(self, fixture_path):
        resolved = load(fixture_path("swarm.yaml"))
        assert isinstance(resolved, ResolvedConfig)
        assert "team" in resolved.orchestrators
        assert "analyst" in resolved.agents
        assert "reporter" in resolved.agents


@pytest.mark.integration
class TestLoadGraphPipeline:
    """Full load() pipeline with graph orchestration."""

    def test_graph_orchestration_wiring(self, fixture_path):
        resolved = load(fixture_path("graph.yaml"))
        assert isinstance(resolved, ResolvedConfig)
        assert "pipeline" in resolved.orchestrators
        assert "collector" in resolved.agents
        assert "analyzer" in resolved.agents
        assert "summarizer" in resolved.agents


@pytest.mark.integration
class TestLoadNestedPipeline:
    """Full load() pipeline with nested orchestrations."""

    def test_nested_orchestration_wiring(self, fixture_path):
        resolved = load(fixture_path("nested_orchestration.yaml"))
        assert isinstance(resolved, ResolvedConfig)
        assert "writing_team" in resolved.orchestrators
        assert "full_pipeline" in resolved.orchestrators
        assert resolved.entry is resolved.orchestrators["full_pipeline"]
