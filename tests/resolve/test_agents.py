"""AgentDef -> strands Agent wiring, via the canonical build_agent_from_def.

Uses real Agent objects built with a FakeModel — no mocks, no private access.
"""

from __future__ import annotations

import pytest
from strands import Agent

from strands_compose.config.resolvers.agents import build_agent_from_def, resolve_agents
from strands_compose.config.schema import SessionManagerDef
from strands_compose.exceptions import ConfigurationError
from tests.factories import agent_def
from tests.fakes import FakeModel


def _models():
    return {"fast": FakeModel()}


def test_agent_is_built_as_plain_strands_agent():
    agent = build_agent_from_def("a", agent_def(model="fast"), _models(), {})
    assert isinstance(agent, Agent)


def test_agent_receives_configured_system_prompt_and_description():
    agent = build_agent_from_def(
        "a",
        agent_def(model="fast", system_prompt="Be terse.", description="tester"),
        _models(),
        {},
    )
    assert agent.system_prompt == "Be terse."
    assert agent.description == "tester"


def test_named_model_reference_is_wired_onto_the_agent():
    model = FakeModel()
    agent = build_agent_from_def("a", agent_def(model="fast"), {"fast": model}, {})
    assert agent.model is model


def test_agent_id_matches_the_config_name():
    agent = build_agent_from_def("greeter", agent_def(model="fast"), _models(), {})
    assert agent.agent_id == "greeter"


def test_resolve_agents_returns_one_agent_per_definition():
    agents = resolve_agents(
        {"a": agent_def(model="fast"), "b": agent_def(model="fast")}, _models(), {}
    )
    assert set(agents) == {"a", "b"}
    assert all(isinstance(a, Agent) for a in agents.values())


def test_custom_factory_returning_non_agent_raises_type_error():
    # builtins:dict is importable and returns a dict, not an Agent.
    bad = agent_def(model="fast", type="builtins:dict")
    with pytest.raises(TypeError):
        build_agent_from_def("a", bad, _models(), {})


def test_swarm_or_graph_node_with_session_manager_fails_fast():
    node = agent_def(model="fast", session_manager=SessionManagerDef(provider="file"))
    with pytest.raises(ConfigurationError):
        build_agent_from_def(
            "a",
            node,
            _models(),
            {},
            orchestration_agent_names={"a"},
        )
