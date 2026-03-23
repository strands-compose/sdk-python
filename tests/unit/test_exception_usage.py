"""Tests verifying correct exception subclass usage in validators and planner."""

from __future__ import annotations

import pytest

from strands_compose.config.loaders.validators import validate_references
from strands_compose.config.resolvers.orchestrations.planner import topological_sort
from strands_compose.config.schema import (
    AgentDef,
    AppConfig,
    GraphEdgeDef,
    GraphOrchestrationDef,
    MCPClientDef,
    SwarmOrchestrationDef,
)
from strands_compose.exceptions import CircularDependencyError, UnresolvedReferenceError


class TestValidatorsRaiseReferenceError:
    """validate_references() should raise UnresolvedReferenceError, not generic ConfigurationError."""

    def test_missing_model_raises_reference_error(self):
        config = AppConfig(
            agents={"a": AgentDef(system_prompt="test", model="nonexistent")},
            entry="a",
        )
        with pytest.raises(UnresolvedReferenceError, match="nonexistent"):
            validate_references(config)

    def test_missing_mcp_client_raises_reference_error(self):
        config = AppConfig(
            agents={"a": AgentDef(system_prompt="test", mcp=["ghost_client"])},
            entry="a",
        )
        with pytest.raises(UnresolvedReferenceError, match="ghost_client"):
            validate_references(config)

    def test_missing_mcp_server_in_client_raises_reference_error(self):
        config = AppConfig(
            agents={"a": AgentDef(system_prompt="test")},
            mcp_clients={"c": MCPClientDef(server="no_such_server")},
            entry="a",
        )
        with pytest.raises(UnresolvedReferenceError, match="no_such_server"):
            validate_references(config)


class TestPlannerRaisesCircularDependencyError:
    """topological_sort() should raise CircularDependencyError for cycles."""

    def test_mutual_dependency_raises_circular_error(self):
        configs = {
            "a": GraphOrchestrationDef(
                entry_name="b",
                edges=[GraphEdgeDef(from_agent="b", to_agent="x")],  # type: ignore[call-arg]
            ),
            "b": GraphOrchestrationDef(
                entry_name="a",
                edges=[GraphEdgeDef(from_agent="a", to_agent="y")],  # type: ignore[call-arg]
            ),
        }
        with pytest.raises(CircularDependencyError, match="Circular dependency"):
            topological_sort(configs)  # type: ignore[arg-type]

    def test_self_referencing_orchestration_raises_circular_error(self):
        configs = {
            "self_loop": SwarmOrchestrationDef(
                entry_name="self_loop",
                agents=["self_loop"],
            ),
        }
        with pytest.raises(CircularDependencyError, match="Circular dependency"):
            topological_sort(configs)  # type: ignore[arg-type]
