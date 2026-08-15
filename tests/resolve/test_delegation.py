"""Delegate wiring — which adapter each connection target gets, and what is rejected.

Result/message extraction (``extractors.py``) is covered in
``runtime/test_result_extraction.py``; this file stays focused on the wrapping.
"""

from __future__ import annotations

import pytest
from strands import Agent
from strands import tool as strands_tool
from strands.hooks import BeforeToolCallEvent
from strands.multiagent import GraphBuilder, Swarm
from strands.session import FileSessionManager
from strands.tools.decorator import DecoratedFunctionTool
from strands.types.tools import AgentTool

from strands_compose.config.resolvers.orchestrations.builders import _delegate_tool
from strands_compose.config.schema import DelegateConnectionDef
from strands_compose.exceptions import ConfigurationError
from strands_compose.tools import multiagent_as_tool
from tests.fakes import FakeModel, ToolThenTextModel


def _agent(agent_id: str, **kwargs) -> Agent:
    return Agent(model=FakeModel(), agent_id=agent_id, **kwargs)


def _swarm(node_id: str) -> Swarm:
    return Swarm(id=node_id, nodes=[_agent("a")], entry_point=None)


def _conn(agent: str, **kwargs) -> DelegateConnectionDef:
    return DelegateConnectionDef(agent=agent, description="do work", **kwargs)


async def _call(tool: AgentTool, prompt: str) -> None:
    async for _ in tool.stream(
        {"toolUseId": "t1", "name": tool.tool_name, "input": {"input": prompt}}, {}
    ):
        pass


# ── multiagent_as_tool ───────────────────────────────────────────────────────


def test_multiagent_as_tool_defaults_name_to_the_orchestration_id():
    tool = multiagent_as_tool(_swarm("team"), description="d")
    assert tool.tool_name == "team"


def test_multiagent_as_tool_accepts_explicit_name():
    tool = multiagent_as_tool(_swarm("team"), name="ask_team", description="d")
    assert tool.tool_name == "ask_team"


# ── adapter choice ───────────────────────────────────────────────────────────


def test_agent_connection_uses_the_strands_native_adapter():
    """An Agent must go through Agent.as_tool so interrupts can propagate and resume."""
    tool = _delegate_tool("team", _conn("helper"), _agent("helper"))

    assert tool.tool_type == "agent"
    assert not isinstance(tool, DecoratedFunctionTool)
    assert tool.tool_name == "helper"


def test_orchestration_connection_falls_back_to_the_multiagent_wrapper():
    """A Swarm has no upstream as_tool, so it keeps the hand-rolled wrapper."""
    tool = _delegate_tool("outer", _conn("team"), _swarm("team"))

    assert isinstance(tool, DecoratedFunctionTool)
    assert tool.tool_name == "team"


def test_tool_name_tracks_the_connection_not_the_node_id():
    """The LLM sees the name the YAML used to reference the target."""
    tool = _delegate_tool("team", _conn("helper"), _agent("helper"))
    assert tool.tool_name == "helper"


# ── preserve_context ─────────────────────────────────────────────────────────


async def test_preserve_context_true_accumulates_history():
    agent = _agent("helper")
    tool = _delegate_tool("team", _conn("helper", preserve_context=True), agent)

    await _call(tool, "first")
    await _call(tool, "second")

    assert len(agent.messages) == 4


async def test_preserve_context_false_resets_between_calls():
    agent = _agent("helper")
    tool = _delegate_tool("team", _conn("helper", preserve_context=False), agent)

    await _call(tool, "first")
    await _call(tool, "second")

    assert len(agent.messages) == 2


def test_preserve_context_defaults_to_preserving_history():
    """Compose defaults to true; strands' Agent.as_tool defaults to false."""
    assert _conn("helper").preserve_context is True


# ── rejected combinations ────────────────────────────────────────────────────


def test_preserve_context_false_with_a_session_manager_is_rejected(tmp_path):
    """strands owns this rule; its error must reach the user unwrapped."""
    agent = _agent(
        "helper",
        session_manager=FileSessionManager(session_id="s1", storage_dir=str(tmp_path)),
    )

    with pytest.raises(ValueError, match="cannot be used with an agent that has a session manager"):
        _delegate_tool("team", _conn("helper", preserve_context=False), agent)


def test_preserve_context_true_allows_a_session_managed_agent(tmp_path):
    agent = _agent(
        "helper",
        session_manager=FileSessionManager(session_id="s2", storage_dir=str(tmp_path)),
    )

    tool = _delegate_tool("team", _conn("helper", preserve_context=True), agent)

    assert tool.tool_name == "helper"


def test_preserve_context_false_on_an_orchestration_is_rejected():
    """A Swarm cannot be reset to a baseline, so the request must not be ignored."""
    with pytest.raises(ConfigurationError, match="no baseline to reset to"):
        _delegate_tool("outer", _conn("team", preserve_context=False), _swarm("team"))


async def test_orchestration_interrupt_becomes_a_tool_error():
    """An interrupt inside a Swarm/Graph cannot be resumed across the boundary.

    Reporting success would make a pending approval look granted, so the caller
    must see an error instead.
    """

    @strands_tool
    def risky(name: str) -> str:
        return f"did {name}"

    worker = Agent(model=ToolThenTextModel(tool_name="risky"), agent_id="worker", tools=[risky])
    worker.add_hook(
        lambda event: event.interrupt(name="approve_risky", reason="needs sign-off"),
        BeforeToolCallEvent,
    )

    builder = GraphBuilder()
    builder.add_node(worker, node_id="worker")
    builder.set_entry_point("worker")
    graph = builder.build()

    tool = _delegate_tool("outer", _conn("pipeline"), graph)

    results = [
        event
        async for event in tool.stream(
            {"toolUseId": "t1", "name": "pipeline", "input": {"input": "go"}}, {}
        )
    ]

    payload = results[-1].tool_result
    assert payload["status"] == "error"
    assert "approve_risky" in payload["content"][0]["text"]
    assert "cannot be resumed" in payload["content"][0]["text"]
