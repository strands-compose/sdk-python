"""AgentDef -> strands Agent wiring, via the canonical build_agent_from_def.

Uses real Agent objects built with a FakeModel — no mocks, no private access.
"""

from __future__ import annotations

import pytest
from strands import Agent
from strands.models import Model

from strands_compose.config.resolvers.agents import build_agent_from_def, resolve_agents
from strands_compose.config.schema import RESERVED_AGENT_KWARGS, SessionManagerDef
from strands_compose.exceptions import ConfigurationError, ImportResolutionError
from tests.factories import agent_def
from tests.fakes import FakeModel, ToolThenTextModel


def _models() -> dict[str, Model]:
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


def test_declared_plugin_contributes_its_tool_to_the_agent():
    # A plugin's @tool reaching agent.tool_names proves the resolved plugins
    # list is passed to Agent(plugins=[...]) and discovered by strands.
    agent = build_agent_from_def(
        "a", agent_def(model="fast", plugins=["tests.fakes:FakePlugin"]), _models(), {}
    )
    assert "fake_plugin_tool" in agent.tool_names


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


def test_every_kwarg_compose_passes_to_a_factory_is_reserved_at_parse_time(tmp_path):
    factory_file = tmp_path / "factory.py"
    factory_file.write_text(
        "from strands import Agent\n\n"
        "def make(**kwargs):\n"
        "    agent = Agent(**kwargs)\n"
        "    agent.state.set('received', sorted(kwargs))\n"
        "    return agent\n"
    )
    schema_file = tmp_path / "schemas.py"
    schema_file.write_text(
        "from pydantic import BaseModel\n\nclass Out(BaseModel):\n    ok: bool\n"
    )

    agent = build_agent_from_def(
        "a",
        agent_def(
            model="fast",
            type=f"{factory_file}:make",
            structured_output={"model": f"{schema_file}:Out", "prompt": "Fill the schema."},
        ),
        _models(),
        {},
    )

    # load_tools_from_directory is reserved but only passed when there is no custom factory.
    assert set(agent.state.get("received")) == set(RESERVED_AGENT_KWARGS) - {
        "load_tools_from_directory"
    }


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


# ── structured output ──────────────────────────────────────────────────────


def _forecast_schema(tmp_path) -> str:
    schema = tmp_path / "schemas.py"
    schema.write_text(
        "from pydantic import BaseModel\n\n\n"
        "class Forecast(BaseModel):\n    city: str\n    temp_c: int\n"
    )
    return f"{schema}:Forecast"


def test_structured_output_makes_the_agent_return_a_typed_result(tmp_path):
    model = ToolThenTextModel(tool_name="Forecast", tool_input='{"city": "Oslo", "temp_c": 3}')
    agent = build_agent_from_def(
        "a",
        agent_def(model="fast", structured_output={"model": _forecast_schema(tmp_path)}),
        {"fast": model},
        {},
    )

    result = agent("Oslo is three degrees")

    output = result.structured_output
    assert output is not None
    assert type(output).__name__ == "Forecast"
    assert output.model_dump() == {"city": "Oslo", "temp_c": 3}


def test_structured_output_that_is_not_a_pydantic_model_raises_type_error():
    with pytest.raises(TypeError):
        build_agent_from_def(
            "a",
            agent_def(model="fast", structured_output={"model": "builtins:dict"}),
            _models(),
            {},
        )


def test_structured_output_with_unknown_import_raises_import_resolution_error():
    with pytest.raises(ImportResolutionError):
        build_agent_from_def(
            "a",
            agent_def(model="fast", structured_output={"model": "no_such_module_xyz:Forecast"}),
            _models(),
            {},
        )
