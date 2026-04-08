"""Tests for orchestrations.builders — build_delegate, build_swarm, build_graph, OrchestrationBuilder."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from strands import Agent as _Agent
from strands.multiagent.base import MultiAgentBase

from strands_compose.config.resolvers.orchestrations.builders import (
    OrchestrationBuilder,
    build_delegate,
    build_graph,
    build_swarm,
)
from strands_compose.config.schema import (
    AgentDef,
    DelegateConnectionDef,
    DelegateOrchestrationDef,
    GraphEdgeDef,
    GraphOrchestrationDef,
    SwarmOrchestrationDef,
)
from strands_compose.exceptions import ConfigurationError

# ---------------------------------------------------------------------------
# build_delegate
# ---------------------------------------------------------------------------


class TestBuildDelegate:
    """build_delegate forks a new agent from entry blueprint with delegate tools."""

    @patch("strands_compose.config.resolvers.orchestrations.builders.build_agent_from_def")
    def test_creates_new_agent_from_blueprint(self, mock_build: MagicMock) -> None:
        """build_delegate constructs a NEW agent via build_agent_from_def."""
        new_agent = MagicMock(spec=_Agent)
        mock_build.return_value = new_agent
        child = MagicMock(spec=_Agent)
        child.agent_id = "child"
        nodes: dict = {"parent": MagicMock(spec=_Agent), "child": child}
        agent_defs: dict = {"parent": AgentDef(system_prompt="I'm the parent")}
        config = DelegateOrchestrationDef(
            entry_name="parent",
            connections=[DelegateConnectionDef(agent="child", description="do work")],
        )

        result = build_delegate("orch", config, nodes, "parent", agent_defs, {}, {})

        # Returns the newly built agent, NOT the original parent.
        assert result is new_agent
        mock_build.assert_called_once()
        call_kwargs = mock_build.call_args
        assert call_kwargs.kwargs["name"] == "orch"
        assert call_kwargs.kwargs["agent_def"] is agent_defs["parent"]
        assert len(call_kwargs.kwargs["extra_tools"]) == 1

    @patch("strands_compose.config.resolvers.orchestrations.builders.build_agent_from_def")
    def test_delegate_accepts_multi_agent_as_child(self, mock_build: MagicMock) -> None:
        """build_delegate can wrap a MultiAgentBase (built orchestration) as a tool."""
        new_agent = MagicMock(spec=_Agent)
        mock_build.return_value = new_agent
        multi_agent = MagicMock(spec=MultiAgentBase)
        multi_agent.id = "my_swarm"
        nodes: dict = {"parent": MagicMock(spec=_Agent), "my_swarm": multi_agent}
        agent_defs: dict = {"parent": AgentDef(system_prompt="I coordinate")}
        config = DelegateOrchestrationDef(
            entry_name="parent",
            connections=[DelegateConnectionDef(agent="my_swarm", description="use swarm")],
        )

        result = build_delegate("orch", config, nodes, "parent", agent_defs, {}, {})

        assert result is new_agent

    def test_entry_not_in_agent_defs_raises(self) -> None:
        """Entry name not in agent_defs raises ConfigurationError."""
        nodes: dict = {"parent": MagicMock(spec=_Agent)}
        config = DelegateOrchestrationDef(
            entry_name="parent",
            connections=[DelegateConnectionDef(agent="child", description="x")],
        )
        with pytest.raises(ConfigurationError, match="must be a declared agent"):
            build_delegate("orch", config, nodes, "parent", {}, {}, {})

    @patch("strands_compose.config.resolvers.orchestrations.builders.build_agent_from_def")
    def test_no_overrides_passes_original_def(self, mock_build: MagicMock) -> None:
        """When no overrides are set the original AgentDef object is passed through."""
        mock_build.return_value = MagicMock(spec=_Agent)
        entry_def = AgentDef(system_prompt="original", agent_kwargs={"max_tool_calls": 5})
        child = MagicMock(spec=_Agent)
        child.agent_id = "child"
        nodes: dict = {"parent": MagicMock(spec=_Agent), "child": child}
        config = DelegateOrchestrationDef(
            entry_name="parent",
            connections=[DelegateConnectionDef(agent="child", description="x")],
        )

        build_delegate("orch", config, nodes, "parent", {"parent": entry_def}, {}, {})

        # No copy should be made — same object passed
        assert mock_build.call_args.kwargs["agent_def"] is entry_def

    @patch("strands_compose.config.resolvers.orchestrations.builders.build_agent_from_def")
    def test_agent_kwargs_merged(self, mock_build: MagicMock) -> None:
        """agent_kwargs are merged: orchestration values override, base keys are inherited."""
        mock_build.return_value = MagicMock(spec=_Agent)
        entry_def = AgentDef(
            agent_kwargs={"max_tool_calls": 5, "trace_attributes": {"env": "test"}}
        )
        child = MagicMock(spec=_Agent)
        child.agent_id = "child"
        nodes: dict = {"parent": MagicMock(spec=_Agent), "child": child}
        config = DelegateOrchestrationDef(
            entry_name="parent",
            connections=[DelegateConnectionDef(agent="child", description="x")],
            agent_kwargs={"max_tool_calls": 50},  # override
        )

        build_delegate("orch", config, nodes, "parent", {"parent": entry_def}, {}, {})

        passed_def = mock_build.call_args.kwargs["agent_def"]
        # orchestration wins on conflict
        assert passed_def.agent_kwargs["max_tool_calls"] == 50
        # base key inherited
        assert passed_def.agent_kwargs["trace_attributes"] == {"env": "test"}
        # original unmodified
        assert entry_def.agent_kwargs["max_tool_calls"] == 5


# ---------------------------------------------------------------------------
# build_swarm
# ---------------------------------------------------------------------------


class TestBuildSwarm:
    """build_swarm creates a Swarm from config and agent nodes."""

    @patch("strands_compose.config.resolvers.orchestrations.builders.Swarm")
    def test_creates_swarm_with_entry_point(self, mock_swarm: MagicMock) -> None:
        """build_swarm instantiates Swarm with the correct entry_point agent."""
        a1 = MagicMock(spec=_Agent)
        a2 = MagicMock(spec=_Agent)
        nodes: dict = {"a1": a1, "a2": a2}
        config = SwarmOrchestrationDef(entry_name="a1", agents=["a1", "a2"])

        build_swarm("test_swarm", config, nodes, "a1")

        mock_swarm.assert_called_once()
        assert mock_swarm.call_args.kwargs["entry_point"] is a1

    def test_raises_on_non_agent_node(self) -> None:
        """Swarm nodes must be plain Agent instances; other types raise ConfigurationError."""
        agent = MagicMock(spec=_Agent)
        non_agent = MagicMock()
        non_agent.__class__.__name__ = "Graph"
        nodes: dict = {"a1": agent, "graph1": non_agent}
        config = SwarmOrchestrationDef(entry_name="a1", agents=["a1", "graph1"])

        with pytest.raises(ConfigurationError, match="must be a plain Agent"):
            build_swarm("test_swarm", config, nodes, "a1")


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------


class TestBuildGraph:
    """build_graph wires agents into a Graph via GraphBuilder."""

    @patch("strands_compose.config.resolvers.orchestrations.builders.GraphBuilder")
    def test_creates_graph_with_nodes_and_edges(self, mock_builder_cls: MagicMock) -> None:
        """build_graph adds all agent nodes, the configured edge, and calls build()."""
        builder = MagicMock()
        mock_builder_cls.return_value = builder
        a1, a2 = MagicMock(), MagicMock()
        nodes: dict = {"a1": a1, "a2": a2}
        config = GraphOrchestrationDef(
            entry_name="a1",
            edges=[GraphEdgeDef(from_agent="a1", to_agent="a2")],  # ty: ignore
        )

        build_graph("test_graph", config, nodes, "a1")

        builder.add_node.assert_called()
        builder.add_edge.assert_called_once_with("a1", "a2", condition=None)
        builder.set_entry_point.assert_called_once_with("a1")
        builder.build.assert_called_once()

    @patch("strands_compose.config.resolvers.orchestrations.builders.GraphBuilder")
    def test_graph_accepts_orchestration_node(self, mock_builder_cls: MagicMock) -> None:
        """Graph supports MultiAgentBase (nested orchestration) as a node."""
        builder = MagicMock()
        mock_builder_cls.return_value = builder
        agent = MagicMock()
        multi_agent = MagicMock()
        nodes: dict = {"agent1": agent, "nested_swarm": multi_agent}
        config = GraphOrchestrationDef(
            entry_name="agent1",
            edges=[
                GraphEdgeDef(from_agent="agent1", to_agent="nested_swarm"),  # ty: ignore
            ],
        )

        build_graph("test_graph", config, nodes, "agent1")

        builder.add_node.assert_any_call(multi_agent, node_id="nested_swarm")


# ---------------------------------------------------------------------------
# OrchestrationBuilder — dispatch and integration
# ---------------------------------------------------------------------------


class TestOrchestrationBuilderDispatch:
    """OrchestrationBuilder raises on unknown config types."""

    def test_unknown_config_type_raises_configuration_error(self) -> None:
        """A config type not matching any known orchestration raises ConfigurationError."""
        a1 = MagicMock(spec=_Agent)
        unknown_cfg = MagicMock()
        unknown_cfg.session_manager = None
        unknown_cfg.entry_name = "a1"
        configs = {"bad": unknown_cfg}

        with pytest.raises(ConfigurationError, match="Unknown orchestration config type"):
            OrchestrationBuilder(configs, {"a1": a1}, {}, {}, {}).build_all()  # ty: ignore


class TestOrchestrationBuilder:
    """OrchestrationBuilder integration: entry resolution, ordering, node pool growth."""

    @patch("strands_compose.config.resolvers.orchestrations.builders.build_agent_from_def")
    def test_delegate_returns_new_agent(self, mock_build: MagicMock) -> None:
        """Delegate produces a new agent — not the original entry agent."""
        original = MagicMock(spec=_Agent)
        new_agent = MagicMock(spec=_Agent)
        mock_build.return_value = new_agent
        child = MagicMock(spec=_Agent)
        child.agent_id = "child"
        agents: dict = {"root": original, "child": child}
        agent_defs: dict = {"root": AgentDef(system_prompt="I coordinate"), "child": AgentDef()}
        configs = {
            "orch": DelegateOrchestrationDef(
                entry_name="root",
                connections=[DelegateConnectionDef(agent="child", description="delegate")],
            ),
        }

        built = OrchestrationBuilder(configs, agents, agent_defs, {}, {}).build_all()  # ty: ignore

        assert built["orch"] is new_agent
        assert built["orch"] is not original

    @patch("strands_compose.config.resolvers.orchestrations.builders.Swarm")
    def test_builds_swarm_in_topological_order(self, mock_swarm_cls: MagicMock) -> None:
        """OrchestrationBuilder correctly builds a single swarm."""
        a1 = MagicMock(spec=_Agent)
        a2 = MagicMock(spec=_Agent)
        agents = {"a1": a1, "a2": a2}
        mock_swarm_cls.return_value = MagicMock()
        configs = {
            "my_swarm": SwarmOrchestrationDef(entry_name="a1", agents=["a1", "a2"]),
        }

        built = OrchestrationBuilder(configs, agents, {}, {}, {}).build_all()  # ty: ignore

        assert "my_swarm" in built
        mock_swarm_cls.assert_called_once()

    @patch("strands_compose.config.resolvers.orchestrations.builders.GraphBuilder")
    @patch("strands_compose.config.resolvers.orchestrations.builders.Swarm")
    def test_node_pool_grows_for_downstream_orchestrations(
        self, mock_swarm_cls: MagicMock, mock_builder_cls: MagicMock
    ) -> None:
        """A graph referencing a named swarm receives the built swarm as a node."""
        a1 = MagicMock(spec=_Agent)
        a2 = MagicMock(spec=_Agent)
        reviewer = MagicMock(spec=_Agent)
        agents = {"a1": a1, "a2": a2, "reviewer": reviewer}
        mock_swarm = MagicMock()
        mock_swarm_cls.return_value = mock_swarm
        builder = MagicMock()
        mock_builder_cls.return_value = builder
        configs = {
            "research_swarm": SwarmOrchestrationDef(entry_name="a1", agents=["a1", "a2"]),
            "pipeline": GraphOrchestrationDef(
                entry_name="research_swarm",
                edges=[
                    GraphEdgeDef(from_agent="research_swarm", to_agent="reviewer"),  # ty: ignore
                ],
            ),
        }

        built = OrchestrationBuilder(configs, agents, {}, {}, {}).build_all()  # ty: ignore

        assert "research_swarm" in built
        assert "pipeline" in built
        builder.add_node.assert_any_call(mock_swarm, node_id="research_swarm")

    @patch("strands_compose.config.resolvers.orchestrations.builders.Swarm")
    def test_session_manager_forwarded_to_swarm(self, mock_swarm_cls: MagicMock) -> None:
        """A session manager passed to OrchestrationBuilder is forwarded to Swarm."""
        a1 = MagicMock(spec=_Agent)
        a2 = MagicMock(spec=_Agent)
        agents = {"a1": a1, "a2": a2}
        sm = MagicMock()
        mock_swarm_cls.return_value = MagicMock()
        configs = {
            "my_swarm": SwarmOrchestrationDef(entry_name="a1", agents=["a1", "a2"]),
        }

        OrchestrationBuilder(configs, agents, {}, {}, {}, sm).build_all()  # ty: ignore

        assert mock_swarm_cls.call_args.kwargs["session_manager"] is sm

    def test_invalid_entry_name_raises_configuration_error(self) -> None:
        """entry_name not in the node pool raises ConfigurationError."""
        a1 = MagicMock(spec=_Agent)
        agents = {"a1": a1}
        configs = {
            "my_swarm": SwarmOrchestrationDef(entry_name="nonexistent", agents=["a1"]),
        }

        with pytest.raises(ConfigurationError, match="entry_name 'nonexistent' is not defined"):
            OrchestrationBuilder(configs, agents, {}, {}, {}).build_all()  # ty: ignore
