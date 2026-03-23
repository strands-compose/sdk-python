"""Tests for orchestrations.planner — collect_node_refs and topological_sort."""

from __future__ import annotations

import pytest

from strands_compose.config.resolvers.orchestrations.planner import (
    collect_node_refs,
    topological_sort,
)
from strands_compose.config.schema import (
    DelegateConnectionDef,
    DelegateOrchestrationDef,
    GraphEdgeDef,
    GraphOrchestrationDef,
    SwarmOrchestrationDef,
)
from strands_compose.exceptions import ConfigurationError


class TestCollectNodeRefs:
    """collect_node_refs extracts all node names referenced by an orchestration."""

    def test_delegate_collects_entry_and_children(self) -> None:
        """Delegate connections include entry_name and all child agent names."""
        config = DelegateOrchestrationDef(
            entry_name="parent",
            connections=[
                DelegateConnectionDef(agent="child1", description="c1"),
                DelegateConnectionDef(agent="child2", description="c2"),
            ],
        )
        assert collect_node_refs(config) == {"parent", "child1", "child2"}

    def test_swarm_collects_all_agents(self) -> None:
        """Swarm refs include all listed agent names."""
        config = SwarmOrchestrationDef(entry_name="a", agents=["a", "b", "c"])
        assert collect_node_refs(config) == {"a", "b", "c"}

    def test_graph_collects_edge_endpoints(self) -> None:
        """Graph refs include both from_agent and to_agent of every edge."""
        config = GraphOrchestrationDef(
            entry_name="a",
            edges=[
                GraphEdgeDef(from_agent="a", to_agent="b"),  # type: ignore[call-arg]
                GraphEdgeDef(from_agent="b", to_agent="c"),  # type: ignore[call-arg]
            ],
        )
        assert collect_node_refs(config) == {"a", "b", "c"}

    def test_delegate_single_connection(self) -> None:
        """Single-connection delegate still returns entry + child."""
        config = DelegateOrchestrationDef(
            entry_name="root",
            connections=[DelegateConnectionDef(agent="leaf", description="leaf")],
        )
        assert collect_node_refs(config) == {"root", "leaf"}


class TestTopologicalSort:
    """topological_sort orders orchestrations so dependencies come first."""

    def test_independent_orchestrations_both_present(self) -> None:
        """Two independent swarms can appear in any order but both are returned."""
        configs = {
            "orch_a": SwarmOrchestrationDef(entry_name="a1", agents=["a1", "a2"]),
            "orch_b": SwarmOrchestrationDef(entry_name="b1", agents=["b1", "b2"]),
        }
        order = topological_sort(configs)  # type: ignore[arg-type]
        assert set(order) == {"orch_a", "orch_b"}

    def test_dependency_appears_before_dependent(self) -> None:
        """orch_b references orch_a as a node -> orch_a must come before orch_b."""
        configs = {
            "orch_a": SwarmOrchestrationDef(entry_name="a1", agents=["a1", "a2"]),
            "orch_b": GraphOrchestrationDef(
                entry_name="orch_a",
                edges=[
                    GraphEdgeDef(from_agent="orch_a", to_agent="reviewer"),  # type: ignore[call-arg]
                ],
            ),
        }
        order = topological_sort(configs)  # type: ignore[arg-type]
        assert order.index("orch_a") < order.index("orch_b")

    def test_circular_dependency_raises_configuration_error(self) -> None:
        """Mutual references between orchestrations raise ConfigurationError."""
        configs = {
            "orch_a": GraphOrchestrationDef(
                entry_name="orch_b",
                edges=[GraphEdgeDef(from_agent="orch_b", to_agent="x")],  # type: ignore[call-arg]
            ),
            "orch_b": GraphOrchestrationDef(
                entry_name="orch_a",
                edges=[GraphEdgeDef(from_agent="orch_a", to_agent="y")],  # type: ignore[call-arg]
            ),
        }
        with pytest.raises(ConfigurationError, match="Circular dependency"):
            topological_sort(configs)  # type: ignore[arg-type]

    def test_three_level_chain_correct_order(self) -> None:
        """A -> B -> C chain: C built first, then B, then A."""
        configs = {
            "A": GraphOrchestrationDef(
                entry_name="B",
                edges=[GraphEdgeDef(from_agent="B", to_agent="agent1")],  # type: ignore[call-arg]
            ),
            "B": GraphOrchestrationDef(
                entry_name="C",
                edges=[GraphEdgeDef(from_agent="C", to_agent="agent2")],  # type: ignore[call-arg]
            ),
            "C": SwarmOrchestrationDef(entry_name="agent3", agents=["agent3", "agent4"]),
        }
        order = topological_sort(configs)  # type: ignore[arg-type]
        assert order.index("C") < order.index("B") < order.index("A")
