"""Dependency resolution — topological sort for named orchestrations.

Provides utilities for ordering named orchestrations and collecting
their node references, used by builders to drive the build pipeline.
"""

from __future__ import annotations

import heapq
import logging
from typing import TYPE_CHECKING

from ....exceptions import CircularDependencyError
from ...schema import (
    DelegateOrchestrationDef,
    GraphOrchestrationDef,
    SwarmOrchestrationDef,
)

if TYPE_CHECKING:
    from ...schema import OrchestrationDef

logger = logging.getLogger(__name__)


def collect_node_refs(config: OrchestrationDef) -> set[str]:
    """Collect all node references from an orchestration config.

    Args:
        config: An orchestration definition.

    Returns:
        Set of node names referenced by this orchestration.
    """
    refs: set[str] = set()
    if isinstance(config, DelegateOrchestrationDef):
        refs.add(config.entry_name)
        for conn in config.connections:
            refs.add(conn.agent)
    elif isinstance(config, SwarmOrchestrationDef):
        refs.update(config.agents)
    elif isinstance(config, GraphOrchestrationDef):
        for edge in config.edges:
            refs.add(edge.from_agent)
            refs.add(edge.to_agent)
    return refs


def topological_sort(
    configs: dict[str, OrchestrationDef],
) -> list[str]:
    """Sort named orchestrations in dependency order.

    An orchestration *depends on* another orchestration when it references
    that orchestration's name as a node. References to plain agents are
    not dependencies.

    Args:
        configs: Dict of orchestration name -> config.

    Returns:
        List of orchestration names in build order (dependencies first).

    Raises:
        ConfigurationError: On circular dependencies between orchestrations.
    """
    orch_names = set(configs)
    deps: dict[str, set[str]] = {}
    for name, cfg in configs.items():
        refs = collect_node_refs(cfg)
        deps[name] = refs & orch_names

    in_degree: dict[str, int] = {n: 0 for n in orch_names}
    for name, dep_set in deps.items():
        for _dep in dep_set:
            in_degree[name] += 1

    queue = sorted(n for n in orch_names if in_degree[n] == 0)
    heapq.heapify(queue)
    order: list[str] = []

    dependents: dict[str, list[str]] = {n: [] for n in orch_names}
    for name, dep_set in deps.items():
        for dep in dep_set:
            dependents[dep].append(name)

    while queue:
        node = heapq.heappop(queue)
        order.append(node)
        for other in dependents[node]:
            in_degree[other] -= 1
            if in_degree[other] == 0:
                heapq.heappush(queue, other)

    if len(order) != len(orch_names):
        remaining = orch_names - set(order)
        raise CircularDependencyError(
            f"Circular dependency between orchestrations: {sorted(remaining)}.\n"
            f"Orchestrations cannot reference each other in a cycle."
        )

    return order
