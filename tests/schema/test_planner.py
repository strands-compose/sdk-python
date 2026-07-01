"""Orchestration dependency ordering and cycle detection."""

from __future__ import annotations

import pytest

from strands_compose.config.resolvers.orchestrations.planner import topological_sort
from strands_compose.exceptions import CircularDependencyError
from tests.factories import delegate_orchestration, swarm_orchestration


def test_dependencies_are_ordered_before_dependents():
    configs = {
        "outer": delegate_orchestration("reviewer", {"inner": "run inner"}),
        "inner": delegate_orchestration("writer", {"researcher": "research"}),
    }
    order = topological_sort(configs)
    assert order.index("inner") < order.index("outer")


def test_independent_orchestrations_all_present():
    configs = {
        "one": delegate_orchestration("a", {"b": "d"}),
        "two": swarm_orchestration("c", ["c", "d"]),
    }
    assert set(topological_sort(configs)) == {"one", "two"}


def test_mutual_dependency_raises_circular():
    configs = {
        "a": delegate_orchestration("x", {"b": "d"}),
        "b": delegate_orchestration("y", {"a": "d"}),
    }
    with pytest.raises(CircularDependencyError):
        topological_sort(configs)


def test_self_reference_raises_circular():
    configs = {"loop": swarm_orchestration("loop", ["loop"])}
    with pytest.raises(CircularDependencyError):
        topological_sort(configs)
