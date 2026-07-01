"""Schema validation contracts — good config validates, bad config raises typed errors.

Asserts on the error *type* (and the offending identifier), never on message prose.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from strands_compose.config.loaders import load_config
from strands_compose.config.schema import AppConfig, MCPClientDef, OrchestrationDef
from strands_compose.exceptions import SchemaValidationError
from tests.factories import agent_def, app_config

# ── AppConfig cross-field validators ───────────────────────────────────────


def test_valid_minimal_config_validates():
    config = app_config()
    assert config.entry == "a"


def test_entry_referencing_unknown_node_raises():
    with pytest.raises(ValidationError, match="ghost"):
        AppConfig(agents={"a": agent_def()}, entry="ghost")


def test_name_collision_across_agents_and_orchestrations_raises():
    from tests.factories import delegate_orchestration

    with pytest.raises(ValidationError, match="dupe"):
        AppConfig(
            agents={"dupe": agent_def(), "helper": agent_def()},
            orchestrations={"dupe": delegate_orchestration("helper", {"helper": "d"})},
            entry="dupe",
        )


# ── MCPClientDef connection-mode validator ─────────────────────────────────


def test_mcp_client_requires_exactly_one_connection_mode_none_set():
    with pytest.raises(ValidationError):
        MCPClientDef()


def test_mcp_client_rejects_multiple_connection_modes():
    with pytest.raises(ValidationError):
        MCPClientDef(server="s", url="http://x")


def test_mcp_client_accepts_single_connection_mode():
    assert MCPClientDef(server="s").server == "s"


# ── Orchestration discriminated union ──────────────────────────────────────


@pytest.mark.parametrize(
    ("mode", "extra"),
    [
        ("delegate", {"entry_name": "a", "connections": [{"agent": "b", "description": "d"}]}),
        ("swarm", {"entry_name": "a", "agents": ["a", "b"]}),
        ("graph", {"entry_name": "a", "edges": [{"from": "a", "to": "b"}]}),
    ],
)
def test_orchestration_union_dispatches_on_mode(mode, extra):
    from pydantic import TypeAdapter

    orch = TypeAdapter(OrchestrationDef).validate_python({"mode": mode, **extra})
    assert orch.mode == mode


def test_orchestration_unknown_mode_raises():
    from pydantic import TypeAdapter

    with pytest.raises(ValidationError):
        TypeAdapter(OrchestrationDef).validate_python({"mode": "quantum", "entry_name": "a"})


def test_graph_edge_accepts_from_to_aliases():
    from strands_compose.config.schema import GraphEdgeDef

    edge = GraphEdgeDef(**{"from": "a", "to": "b"})
    assert (edge.from_agent, edge.to_agent) == ("a", "b")


# ── load_config surfaces schema failures as the typed subclass ─────────────


def test_load_config_wraps_schema_failure_as_schema_validation_error():
    # 'agents' must be a mapping; a list is a schema violation.
    with pytest.raises(SchemaValidationError):
        load_config("agents: [not, a, mapping]\nentry: a")
