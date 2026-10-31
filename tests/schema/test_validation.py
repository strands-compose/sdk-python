"""Schema validation contracts — good config validates, bad config raises typed errors.

Asserts on the error *type* (and the offending identifier), never on message prose.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from strands_compose.config.loaders import load_config
from strands_compose.config.schema import AppConfig, OrchestrationDef
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


# ── models: cache ───────────────────────────────────────────────────────────

_CACHE_CONFIG = """
models:
  m:
    provider: bedrock
    model_id: x
{model_lines}
agents:
  a: {{model: m, system_prompt: hi}}
entry: a
"""


@pytest.mark.parametrize(
    "model_lines",
    ["    cache: true", "    cache: {strategy: auto, ttl: 1h}", "    cache: false"],
)
def test_model_cache_bool_or_mapping_validates(model_lines):
    config = load_config(_CACHE_CONFIG.format(model_lines=model_lines))
    assert "m" in config.models


@pytest.mark.parametrize(
    "model_lines",
    [
        "    cache: 1",
        "    cache: 'yes'",
        "    cache: {bogus: 1}",
        "    cache: {strategy: nope}",
        "    params: {cache_config: {strategy: auto}}",
    ],
)
def test_model_cache_wrong_type_or_params_cache_config_raises(model_lines):
    with pytest.raises(SchemaValidationError):
        load_config(_CACHE_CONFIG.format(model_lines=model_lines))


# ── agent_kwargs must not carry keys that compose passes itself ────────────


@pytest.mark.parametrize(
    "key",
    [
        "system_prompt",
        "conversation_manager",
        "tools",
        "load_tools_from_directory",
    ],
)
def test_agent_kwargs_with_reserved_key_raises_schema_validation_error(key):
    config = f"""
agents:
  a:
    system_prompt: hi
    agent_kwargs:
      {key}: x
entry: a
"""
    with pytest.raises(SchemaValidationError, match=key):
        load_config(config)


def test_delegate_agent_kwargs_with_reserved_key_raises_schema_validation_error():
    config = """
agents:
  a:
    system_prompt: hi
  b:
    system_prompt: hi
orchestrations:
  team:
    mode: delegate
    entry_name: a
    connections:
      - agent: b
        description: helper
    agent_kwargs:
      system_prompt: override
entry: team
"""
    with pytest.raises(SchemaValidationError, match="system_prompt"):
        load_config(config)


def test_agent_kwargs_with_regular_agent_parameter_validates():
    config = app_config(agents={"a": agent_def(agent_kwargs={"record_direct_tool_call": False})})
    assert config.agents["a"].agent_kwargs == {"record_direct_tool_call": False}
