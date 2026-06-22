"""Tests for strands_compose.manifest — pure manifest builders."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from strands import Agent
from strands.multiagent import Swarm
from strands.multiagent.graph import Graph
from strands.session import FileSessionManager, S3SessionManager

from strands_compose.manifest import (
    build_manifest,
    build_session_manager_descriptor,
)
from strands_compose.types import (
    AgentCoreProviderDescriptor,
    CustomProviderDescriptor,
    FileProviderDescriptor,
    S3ProviderDescriptor,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_agent(
    description: str | None = None,
    model_id: str | None = None,
    session_manager: object | None = None,
) -> Agent:
    """Create a mock Agent suitable for manifest building."""
    agent = Mock(spec=Agent)
    agent.description = description
    agent.model = Mock()
    config = {"model_id": model_id} if model_id else {}
    agent.model.get_config.return_value = config
    agent.model.__class__.__module__ = "strands.models"
    agent.model.__class__.__qualname__ = "TestModel"
    agent._session_manager = session_manager
    return agent  # type: ignore[return-value]


# ── build_session_manager_descriptor ─────────────────────────────────────────


class TestBuildSessionManagerDescriptor:
    """Tests for build_session_manager_descriptor."""

    def test_file_session_manager_descriptor(self, tmp_path):
        """FileSessionManager → FileProviderDescriptor."""
        storage_dir = str(tmp_path / "sessions")
        manager = FileSessionManager(session_id="sess-123", storage_dir=storage_dir)
        descriptor = build_session_manager_descriptor(manager)

        assert isinstance(descriptor, FileProviderDescriptor)
        assert descriptor.provider == "file"
        assert descriptor.session_id == "sess-123"
        assert descriptor.storage_dir == storage_dir

    def test_s3_session_manager_descriptor(self):
        """S3SessionManager → S3ProviderDescriptor."""
        manager = Mock(spec=S3SessionManager)
        manager.session_id = "sess-456"
        manager.bucket = "my-bucket"
        manager.prefix = "sessions/"

        descriptor = build_session_manager_descriptor(manager)

        assert isinstance(descriptor, S3ProviderDescriptor)
        assert descriptor.provider == "s3"
        assert descriptor.session_id == "sess-456"
        assert descriptor.bucket == "my-bucket"
        assert descriptor.prefix == "sessions/"

    def test_s3_session_manager_descriptor_empty_prefix(self):
        """S3SessionManager with empty prefix."""
        manager = Mock(spec=S3SessionManager)
        manager.session_id = "sess-789"
        manager.bucket = "bucket"
        manager.prefix = ""

        descriptor = build_session_manager_descriptor(manager)

        assert isinstance(descriptor, S3ProviderDescriptor)
        assert descriptor.prefix == ""

    def test_agentcore_duck_typed_descriptor(self):
        """Duck-typed AgentCore manager → AgentCoreProviderDescriptor."""
        manager = Mock(spec=[])
        manager.config = Mock(spec=["memory_id", "actor_id", "session_id"])
        manager.config.memory_id = "mem-123"
        manager.config.actor_id = "actor-456"
        manager.config.session_id = "sess-789"

        descriptor = build_session_manager_descriptor(manager)

        assert isinstance(descriptor, AgentCoreProviderDescriptor)
        assert descriptor.provider == "agentcore"
        assert descriptor.session_id == "sess-789"
        assert descriptor.memory_id == "mem-123"
        assert descriptor.actor_id == "actor-456"

    def test_custom_session_manager_descriptor(self):
        """Unknown manager type → CustomProviderDescriptor."""
        manager = Mock(spec=[])
        manager.session_id = "sess-custom"

        descriptor = build_session_manager_descriptor(manager)

        assert isinstance(descriptor, CustomProviderDescriptor)
        assert descriptor.provider == "custom"
        assert descriptor.session_id == "sess-custom"
        assert "Mock" in descriptor.class_name

    def test_custom_session_manager_descriptor_no_session_id(self):
        """Custom manager without session_id → session_id is None."""
        manager = Mock(spec=[])

        descriptor = build_session_manager_descriptor(manager)

        assert isinstance(descriptor, CustomProviderDescriptor)
        assert descriptor.provider == "custom"
        assert descriptor.session_id is None

    def test_custom_descriptor_class_name_fully_qualified(self):
        """CustomProviderDescriptor.class_name is fully-qualified."""
        manager = Mock(spec=[])
        manager.session_id = None

        descriptor = build_session_manager_descriptor(manager)

        assert isinstance(descriptor, CustomProviderDescriptor)
        assert "." in descriptor.class_name
        assert descriptor.class_name.startswith("unittest.mock")


# ── build_manifest ───────────────────────────────────────────────────────────


class TestBuildManifest:
    """Tests for build_manifest."""

    def test_manifest_with_single_agent(self):
        """Manifest with one agent."""
        agent = _mock_agent(description="Test agent", model_id="gpt-4")

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={},
            entry=agent,
        )

        assert len(manifest.agents) == 1
        assert manifest.agents[0].name == "agent1"
        assert manifest.agents[0].description == "Test agent"
        assert manifest.agents[0].model.model_id == "gpt-4"
        assert "TestModel" in manifest.agents[0].model.provider
        assert manifest.agents[0].session_manager is None

    def test_manifest_agent_description_none(self):
        """Agent with None description."""
        agent = _mock_agent(description=None)

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={},
            entry=agent,
        )

        assert manifest.agents[0].description is None

    def test_manifest_agent_model_id_from_dict_config(self):
        """Extract model_id from dict config."""
        agent = _mock_agent(model_id="claude-3")

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={},
            entry=agent,
        )

        assert manifest.agents[0].model.model_id == "claude-3"

    def test_manifest_agent_model_id_from_object_config(self):
        """Extract model_id from object config via getattr."""
        agent = Mock(spec=Agent)
        agent.description = None
        config_obj = Mock()
        config_obj.model_id = "custom-model"
        agent.model = Mock()
        agent.model.get_config.return_value = config_obj
        agent.model.__class__.__module__ = "custom"
        agent.model.__class__.__qualname__ = "CustomModel"
        agent._session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={},
            entry=agent,
        )

        assert manifest.agents[0].model.model_id == "custom-model"

    def test_manifest_agent_model_id_none_when_absent(self):
        """model_id is None when not in config."""
        agent = _mock_agent()  # no model_id

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={},
            entry=agent,
        )

        assert manifest.agents[0].model.model_id is None

    def test_manifest_agent_session_manager_none(self):
        """session_manager is None when agent has no session manager."""
        agent = _mock_agent()

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={},
            entry=agent,
        )

        assert manifest.agents[0].session_manager is None

    def test_manifest_entry_not_found_raises_value_error(self):
        """ValueError when entry not found in agents or orchestrators."""
        agent = _mock_agent()
        other_agent = Mock(spec=Agent)

        with pytest.raises(ValueError, match="entry node not found"):
            build_manifest(
                agents={"agent1": agent},
                orchestrators={},
                entry=other_agent,
            )

    def test_manifest_orchestration_kind_delegate(self):
        """Agent orchestration → kind='delegate'; delegate also appears in agents."""
        agent = _mock_agent()
        delegate = Mock(spec=Agent)
        delegate._session_manager = None
        delegate.description = None
        delegate.model = Mock()
        delegate.model.get_config.return_value = {}
        delegate.model.__class__.__module__ = "strands.models"
        delegate.model.__class__.__qualname__ = "TestModel"

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"delegate1": delegate},
            entry=delegate,
        )

        assert len(manifest.orchestrations) == 1
        assert manifest.orchestrations[0].kind == "delegate"
        assert manifest.orchestrations[0].nodes == []
        assert manifest.orchestrations[0].edges is None
        assert manifest.orchestrations[0].entry_node_id is None
        # Delegate agent is also included in manifest.agents under its orch name
        agent_names = [a.name for a in manifest.agents]
        assert "agent1" in agent_names
        assert "delegate1" in agent_names

    def test_manifest_orchestration_kind_swarm(self):
        """Swarm orchestration → kind='swarm'."""
        agent = _mock_agent()
        swarm = Mock(spec=Swarm)
        swarm.nodes = {}
        swarm.entry_point = None
        swarm.session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"swarm1": swarm},
            entry=swarm,
        )

        assert len(manifest.orchestrations) == 1
        assert manifest.orchestrations[0].kind == "swarm"

    def test_manifest_orchestration_kind_graph(self):
        """Graph orchestration → kind='graph'."""
        agent = _mock_agent()
        graph = Mock(spec=Graph)
        graph.nodes = {}
        graph.edges = set()
        graph.entry_points = set()
        graph.session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"graph1": graph},
            entry=graph,
        )

        assert len(manifest.orchestrations) == 1
        assert manifest.orchestrations[0].kind == "graph"

    def test_manifest_orchestration_kind_unknown(self):
        """Unknown orchestration type → kind='unknown'."""
        agent = _mock_agent()
        unknown = Mock()  # Not Agent, Swarm, or Graph

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"unknown1": unknown},
            entry=unknown,
        )

        assert len(manifest.orchestrations) == 1
        assert manifest.orchestrations[0].kind == "unknown"

    def test_manifest_entry_descriptor_agent(self):
        """Entry descriptor for agent entry."""
        agent = _mock_agent()

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={},
            entry=agent,
        )

        assert manifest.entry.name == "agent1"
        assert manifest.entry.kind == "agent"

    def test_manifest_entry_descriptor_orchestration(self):
        """Entry descriptor for orchestration entry."""
        agent = _mock_agent()
        swarm = Mock(spec=Swarm)
        swarm.nodes = {}
        swarm.entry_point = None
        swarm.session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"swarm1": swarm},
            entry=swarm,
        )

        assert manifest.entry.name == "swarm1"
        assert manifest.entry.kind == "orchestration"

    def test_manifest_insertion_order_preserved_agents(self):
        """Agent descriptor order matches dict insertion order."""
        agents = {f"agent{i}": _mock_agent() for i in range(3)}

        manifest = build_manifest(
            agents=agents,
            orchestrators={},
            entry=agents["agent0"],
        )

        assert [d.name for d in manifest.agents] == ["agent0", "agent1", "agent2"]

    def test_manifest_insertion_order_preserved_orchestrations(self):
        """Orchestration descriptor order matches dict insertion order."""
        agent = _mock_agent()

        orchestrators = {}
        for i in range(3):
            orch = Mock(spec=Swarm)
            orch.nodes = {}
            orch.entry_point = None
            orch.session_manager = None
            orchestrators[f"orch{i}"] = orch

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators=orchestrators,
            entry=agent,
        )

        assert [d.name for d in manifest.orchestrations] == ["orch0", "orch1", "orch2"]

    def test_manifest_swarm_nodes_and_entry_point(self):
        """Swarm nodes and entry_point resolved correctly."""
        agent = _mock_agent()

        swarm_node1 = Mock()
        swarm_node1.node_id = "node1"
        swarm_node1.executor = agent

        swarm_node2 = Mock()
        swarm_node2.node_id = "node2"
        swarm_node2.executor = Mock(spec=Agent)

        swarm = Mock(spec=Swarm)
        swarm.nodes = {"node1": swarm_node1, "node2": swarm_node2}
        swarm.entry_point = agent
        swarm.session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"swarm1": swarm},
            entry=swarm,
        )

        orch_desc = manifest.orchestrations[0]
        assert len(orch_desc.nodes) == 2
        assert orch_desc.nodes[0].id == "node1"
        assert orch_desc.nodes[0].kind == "agent"
        assert orch_desc.entry_node_id == "node1"

    def test_manifest_swarm_entry_point_none_uses_first_node(self):
        """Swarm with no entry_point uses first node."""
        agent = _mock_agent()

        swarm_node = Mock()
        swarm_node.node_id = "first"
        swarm_node.executor = agent

        swarm = Mock(spec=Swarm)
        swarm.nodes = {"first": swarm_node}
        swarm.entry_point = None
        swarm.session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"swarm1": swarm},
            entry=swarm,
        )

        assert manifest.orchestrations[0].entry_node_id == "first"

    def test_manifest_swarm_empty_nodes_entry_node_id_none(self):
        """Swarm with no nodes has entry_node_id=None."""
        agent = _mock_agent()

        swarm = Mock(spec=Swarm)
        swarm.nodes = {}
        swarm.entry_point = None
        swarm.session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"swarm1": swarm},
            entry=swarm,
        )

        assert manifest.orchestrations[0].entry_node_id is None

    def test_manifest_graph_nodes_and_edges(self):
        """Graph nodes and edges resolved correctly."""
        agent = _mock_agent()

        graph_node1 = Mock()
        graph_node1.node_id = "gnode1"
        graph_node1.executor = agent

        graph_node2 = Mock()
        graph_node2.node_id = "gnode2"
        graph_node2.executor = Mock(spec=Agent)

        graph_edge = Mock()
        graph_edge.from_node = graph_node1
        graph_edge.to_node = graph_node2

        graph = Mock(spec=Graph)
        graph.nodes = {"gnode1": graph_node1, "gnode2": graph_node2}
        graph.edges = {graph_edge}
        graph.entry_points = {graph_node1}
        graph.session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"graph1": graph},
            entry=graph,
        )

        orch_desc = manifest.orchestrations[0]
        assert len(orch_desc.nodes) == 2
        assert orch_desc.nodes[0].id == "gnode1"
        assert orch_desc.nodes[0].kind == "agent"
        assert orch_desc.edges is not None
        assert len(orch_desc.edges) == 1
        assert orch_desc.edges[0].from_id == "gnode1"
        assert orch_desc.edges[0].to_id == "gnode2"

    def test_manifest_graph_entry_node_id_single(self):
        """Graph with single entry point."""
        agent = _mock_agent()

        graph_node = Mock()
        graph_node.node_id = "entry"

        graph = Mock(spec=Graph)
        graph.nodes = {"entry": graph_node}
        graph.edges = set()
        graph.entry_points = {graph_node}
        graph.session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"graph1": graph},
            entry=graph,
        )

        assert manifest.orchestrations[0].entry_node_id == "entry"

    def test_manifest_graph_entry_node_id_multiple_comma_joined(self):
        """Graph with multiple entry points → comma-joined."""
        agent = _mock_agent()

        graph_node1 = Mock()
        graph_node1.node_id = "entry1"

        graph_node2 = Mock()
        graph_node2.node_id = "entry2"

        graph = Mock(spec=Graph)
        graph.nodes = {"entry1": graph_node1, "entry2": graph_node2}
        graph.edges = set()
        # Use a list to preserve order for testing
        graph.entry_points = [graph_node1, graph_node2]
        graph.session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"graph1": graph},
            entry=graph,
        )

        entry_id = manifest.orchestrations[0].entry_node_id
        assert entry_id is not None
        assert "entry1" in entry_id
        assert "entry2" in entry_id
        assert "," in entry_id

    def test_manifest_graph_entry_node_id_none_when_empty(self):
        """Graph with no entry points → entry_node_id=None."""
        agent = _mock_agent()

        graph = Mock(spec=Graph)
        graph.nodes = {}
        graph.edges = set()
        graph.entry_points = set()
        graph.session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"graph1": graph},
            entry=graph,
        )

        assert manifest.orchestrations[0].entry_node_id is None

    def test_manifest_delegate_empty_topology(self):
        """Delegate orchestration has empty topology; delegate appears in agents."""
        agent = _mock_agent()
        delegate = Mock(spec=Agent)
        delegate._session_manager = None
        delegate.description = None
        delegate.model = Mock()
        delegate.model.get_config.return_value = {}
        delegate.model.__class__.__module__ = "strands.models"
        delegate.model.__class__.__qualname__ = "TestModel"

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"delegate1": delegate},
            entry=delegate,
        )

        orch_desc = manifest.orchestrations[0]
        assert orch_desc.nodes == []
        assert orch_desc.edges is None
        assert orch_desc.entry_node_id is None
        assert len(manifest.agents) == 2
        assert {a.name for a in manifest.agents} == {"agent1", "delegate1"}

    def test_manifest_delegate_agent_descriptor_uses_orchestration_name(self):
        """Delegate added to agents uses the orchestration name, not the entry agent name."""
        agent = _mock_agent(model_id="claude-3")
        delegate = Mock(spec=Agent)
        delegate._session_manager = None
        delegate.description = "orchestrator"
        delegate.model = Mock()
        delegate.model.get_config.return_value = {"model_id": "claude-3"}
        delegate.model.__class__.__module__ = "strands.models"
        delegate.model.__class__.__qualname__ = "TestModel"

        manifest = build_manifest(
            agents={"manager": agent},
            orchestrators={"main": delegate},
            entry=delegate,
        )

        delegate_agent = next(a for a in manifest.agents if a.name == "main")
        assert delegate_agent.model.model_id == "claude-3"

    def test_manifest_non_delegate_orchestration_not_added_to_agents(self):
        """Swarm and Graph orchestrations are not added to manifest.agents."""
        agent = _mock_agent()
        swarm = Mock(spec=Swarm)
        swarm.nodes = {}
        swarm.entry_point = None
        swarm.session_manager = None

        manifest = build_manifest(
            agents={"agent1": agent},
            orchestrators={"swarm1": swarm},
            entry=swarm,
        )

        assert len(manifest.agents) == 1
        assert manifest.agents[0].name == "agent1"
