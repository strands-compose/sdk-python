"""Delegate wiring — which adapter each connection target gets, and what is rejected.

Result/message extraction (``extractors.py``) is covered in
``runtime/test_result_extraction.py``; this file stays focused on the wrapping.
"""

from __future__ import annotations

import asyncio

import pytest
from strands import Agent
from strands import tool as strands_tool
from strands.hooks import BeforeToolCallEvent
from strands.multiagent import GraphBuilder, Swarm
from strands.session import FileSessionManager
from strands.tools.decorator import DecoratedFunctionTool
from strands.types.tools import AgentTool, ToolResult, ToolUse

from strands_compose.config.resolvers.orchestrations.builders import build_delegate
from strands_compose.config.schema import (
    AgentDef,
    DelegateConnectionDef,
    DelegateOrchestrationDef,
)
from strands_compose.exceptions import ConfigurationError
from strands_compose.tools import multiagent_as_tool
from strands_compose.types import Node
from tests.fakes import BoomModel, FakeModel, ToolThenTextModel


def _agent(agent_id: str, **kwargs) -> Agent:
    return Agent(model=FakeModel(), agent_id=agent_id, **kwargs)


def _swarm(node_id: str) -> Swarm:
    return Swarm(id=node_id, nodes=[_agent("a")], entry_point=None)


def _conn(agent: str, **kwargs) -> DelegateConnectionDef:
    return DelegateConnectionDef(agent=agent, description="do work", **kwargs)


def _build_delegate_tool(orch_name: str, conn: DelegateConnectionDef, node: Node) -> AgentTool:
    """Build a real delegate orchestration and return the tool wired for *conn*.

    Nothing is faked: ``build_delegate`` runs for real and the tool comes out of
    the built agent's registry.
    """
    coordinator = "coordinator"
    agent = build_delegate(
        orch_name,
        DelegateOrchestrationDef(entry_name=coordinator, connections=[conn]),
        {coordinator: _agent(coordinator), conn.agent: node},
        coordinator,
        {coordinator: AgentDef(system_prompt="coordinate")},
        {},
        {},
    )
    return agent.tool_registry.registry[conn.agent]


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
    tool = _build_delegate_tool("team", _conn("helper"), _agent("helper"))

    assert tool.tool_type == "agent"
    assert not isinstance(tool, DecoratedFunctionTool)
    assert tool.tool_name == "helper"


def test_orchestration_connection_falls_back_to_the_multiagent_wrapper():
    """A Swarm has no upstream as_tool, so it keeps the hand-rolled wrapper."""
    tool = _build_delegate_tool("outer", _conn("team"), _swarm("team"))

    assert isinstance(tool, DecoratedFunctionTool)
    assert tool.tool_name == "team"


# ── preserve_context ─────────────────────────────────────────────────────────


async def test_preserve_context_true_accumulates_history():
    agent = _agent("helper")
    tool = _build_delegate_tool("team", _conn("helper", preserve_context=True), agent)

    await _call(tool, "first")
    await _call(tool, "second")

    assert len(agent.messages) == 4


async def test_preserve_context_false_resets_between_calls():
    agent = _agent("helper")
    tool = _build_delegate_tool("team", _conn("helper", preserve_context=False), agent)

    await _call(tool, "first")
    await _call(tool, "second")

    assert len(agent.messages) == 2


# ── rejected combinations ────────────────────────────────────────────────────


def test_preserve_context_false_with_a_session_manager_is_rejected(tmp_path):
    """strands owns this rule; its error must reach the user unwrapped."""
    agent = _agent(
        "helper",
        session_manager=FileSessionManager(session_id="s1", storage_dir=str(tmp_path)),
    )

    with pytest.raises(ValueError, match="session manager"):
        _build_delegate_tool("team", _conn("helper", preserve_context=False), agent)


def test_preserve_context_true_allows_a_session_managed_agent(tmp_path):
    agent = _agent(
        "helper",
        session_manager=FileSessionManager(session_id="s2", storage_dir=str(tmp_path)),
    )

    tool = _build_delegate_tool("team", _conn("helper", preserve_context=True), agent)

    assert tool.tool_name == "helper"


def test_preserve_context_false_on_an_orchestration_is_rejected():
    """A Swarm cannot be reset to a baseline, so the request must not be ignored."""
    with pytest.raises(ConfigurationError, match="no baseline to reset to"):
        _build_delegate_tool("outer", _conn("team", preserve_context=False), _swarm("team"))


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

    tool = _build_delegate_tool("outer", _conn("pipeline"), graph)

    results = [
        event
        async for event in tool.stream(
            {"toolUseId": "t1", "name": "pipeline", "input": {"input": "go"}},
            {"agent": _agent("caller")},
        )
    ]

    payload = results[-1].tool_result
    assert payload["status"] == "error"
    assert "approve_risky" in payload["content"][0]["text"]


def _tool_result(agent: Agent) -> ToolResult:
    """Return the last tool result in the agent's history."""
    return next(
        block["toolResult"]
        for message in reversed(agent.messages)
        for block in message["content"]
        if "toolResult" in block
    )


def _caller(tool: AgentTool) -> Agent:
    """An agent whose model calls ``tool`` once with the prompt ``go``."""
    return Agent(
        model=ToolThenTextModel(tool_name=tool.tool_name, tool_input='{"input": "go"}'),
        tools=[tool],
    )


def test_failed_swarm_is_reported_to_the_caller_as_a_tool_error():
    swarm = Swarm(id="team", nodes=[Agent(model=BoomModel(), agent_id="a")], entry_point=None)
    caller = _caller(multiagent_as_tool(swarm, description="d"))

    caller("delegate")

    assert _tool_result(caller)["status"] == "error"


def test_swarm_stopped_by_its_handoff_limit_is_reported_as_a_tool_error():
    ping = Agent(
        model=ToolThenTextModel(
            tool_name="handoff_to_agent", tool_input='{"agent_name": "pong", "message": "x"}'
        ),
        name="ping",
    )
    pong = Agent(
        model=ToolThenTextModel(
            tool_name="handoff_to_agent", tool_input='{"agent_name": "ping", "message": "x"}'
        ),
        name="pong",
    )
    swarm = Swarm(id="team", nodes=[ping, pong], entry_point=ping, max_handoffs=1)
    caller = _caller(multiagent_as_tool(swarm, description="d"))

    caller("delegate")

    assert _tool_result(caller)["status"] == "error"


def test_finished_swarm_is_reported_to_the_caller_as_success():
    swarm = Swarm(id="team", nodes=[_agent("a")], entry_point=None)
    caller = _caller(multiagent_as_tool(swarm, description="d"))

    caller("delegate")

    assert _tool_result(caller)["status"] == "success"


def test_swarm_tokens_count_toward_the_calling_request():
    swarm = Swarm(id="team", nodes=[_agent("a")], entry_point=None)
    caller = _caller(multiagent_as_tool(swarm, description="d"))

    result = caller("delegate")

    assert result.invocation_context is not None
    caller_only = caller.event_loop_metrics.accumulated_usage["totalTokens"]
    assert result.invocation_context.usage["totalTokens"] > caller_only


async def test_second_concurrent_call_to_the_same_tool_is_rejected():
    entered = asyncio.Event()
    release = asyncio.Event()

    @strands_tool
    async def wait_for_release(name: str) -> str:
        """Block until the test releases it."""
        entered.set()
        await release.wait()
        return name

    worker = Agent(
        model=ToolThenTextModel(tool_name="wait_for_release"),
        agent_id="worker",
        tools=[wait_for_release],
    )
    tool = multiagent_as_tool(Swarm(id="team", nodes=[worker], entry_point=None), description="d")
    tool_use: ToolUse = {"toolUseId": "t1", "name": "team", "input": {"input": "go"}}
    state = {"agent": _agent("caller")}

    async def _final_result():
        return [event async for event in tool.stream(tool_use, state)][-1].tool_result

    first = asyncio.create_task(_final_result())
    await entered.wait()
    second = await _final_result()
    release.set()
    first_result = await first

    assert second["status"] == "error"
    assert first_result["status"] == "success"
