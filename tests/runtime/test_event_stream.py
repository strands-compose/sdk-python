"""StreamEvent translation through the real event loop + make_event_queue.

Drives real strands agents with FakeModels — the highest-fidelity way to prove
EventPublisher's translation without touching its private handlers.
"""

from __future__ import annotations

import asyncio
import logging

from strands import Agent, tool
from strands.middleware import InvokeModelStage
from strands.multiagent import GraphBuilder, Swarm

from strands_compose.config import load
from strands_compose.config.schema import AppConfig
from strands_compose.hooks import EventPublisher
from strands_compose.types import EventType, Node
from strands_compose.wire import make_event_queue
from tests.factories import agent_def
from tests.fakes import BoomModel, FakeModel, ToolThenTextModel

logger = logging.getLogger(__name__)


async def _drain(eq) -> list:
    events = []
    while True:
        ev = await eq.get()
        if ev is None:
            break
        events.append(ev)
    return events


async def _run_agent(prompt: str, agent: Node, eq) -> list:
    async def _invoke() -> None:
        try:
            await agent.invoke_async(prompt)
        except Exception:
            logger.debug("invoke_async raised (expected for BoomModel cases)", exc_info=True)
        finally:
            await eq.close()

    task: asyncio.Task[None] = asyncio.create_task(_invoke())
    events = await _drain(eq)
    await task  # ensure the task finishes and any exception surfaces
    return events


async def test_text_response_emits_start_tokens_and_complete():
    agent = Agent(model=FakeModel(["Hello", " world"]))
    eq = make_event_queue({"assistant": agent}, entry_name="assistant")

    events = await _run_agent("hi", agent, eq)
    kinds = [e.type for e in events]

    assert EventType.AGENT_START in kinds
    assert EventType.AGENT_COMPLETE in kinds
    tokens = [e.data["text"] for e in events if e.type == EventType.TOKEN]
    assert "".join(tokens) == "Hello world"


async def test_reasoning_text_emits_reasoning_events():
    agent = Agent(model=FakeModel(["answer"], reasoning_chunks=["let me ", "think"]))
    eq = make_event_queue({"a": agent}, entry_name="a")

    events = await _run_agent("hi", agent, eq)
    reasoning = [e.data["text"] for e in events if e.type == EventType.REASONING]

    assert "".join(reasoning) == "let me think"


async def test_custom_callback_handler_is_kept_and_still_receives_events():
    received: list[dict] = []

    def handler(**kwargs) -> None:
        received.append(kwargs)

    agent = Agent(model=FakeModel(["Hello"]), callback_handler=handler)
    eq = make_event_queue({"a": agent}, entry_name="a")

    events = await _run_agent("hi", agent, eq)

    assert agent.callback_handler is handler
    assert any(kwargs.get("data") == "Hello" for kwargs in received)
    assert any(e.type == EventType.TOKEN for e in events)


async def test_default_printing_handler_is_silenced_on_a_queue_wired_agent(capsys):
    agent = Agent(model=FakeModel(["Hello"]))
    eq = make_event_queue({"a": agent}, entry_name="a")

    await _run_agent("hi", agent, eq)

    assert capsys.readouterr().out == ""


async def test_delegated_agent_tokens_appear_once_under_its_own_name():
    helper = Agent(name="helper", model=FakeModel(["from-helper"]))
    coordinator = Agent(
        name="coordinator",
        model=ToolThenTextModel(tool_name="helper", tool_input='{"input": "go"}'),
        tools=[helper.as_tool(name="helper", description="Ask the helper.")],
    )
    eq = make_event_queue(
        {"helper": helper}, orchestrators={"coordinator": coordinator}, entry_name="coordinator"
    )

    events = await _run_agent("hi", coordinator, eq)
    helper_tokens = [
        e for e in events if e.type == EventType.TOKEN and "from-helper" in e.data["text"]
    ]

    assert [e.agent_name for e in helper_tokens] == ["helper"]


async def test_broken_consumer_callback_does_not_break_the_invocation():
    def _consumer_gone(_event) -> None:
        raise RuntimeError("consumer disconnected")

    publisher = EventPublisher(callback=_consumer_gone, agent_name="a")
    agent = Agent(model=FakeModel(["Hello"]), hooks=[publisher])
    agent.add_middleware(InvokeModelStage, publisher.observe_model_stream)

    result = await agent.invoke_async("hi")

    assert str(result).strip() == "Hello"


async def test_agent_complete_includes_model_id_and_provider():
    agent = Agent(model=FakeModel(["hi"], model_id="us.anthropic.claude-sonnet-4-6"))
    eq = make_event_queue({"a": agent}, entry_name="a")

    events = await _run_agent("hi", agent, eq)
    complete = next(e for e in events if e.type == EventType.AGENT_COMPLETE)

    assert complete.data["model"]["model_id"] == "us.anthropic.claude-sonnet-4-6"
    assert complete.data["model"]["provider"] == f"{FakeModel.__module__}.{FakeModel.__qualname__}"


async def test_tool_call_emits_tool_start_and_success_end():
    @tool
    def greet(name: str) -> str:
        """Greet."""
        return f"Hi {name}"

    agent = Agent(model=ToolThenTextModel(tool_name="greet"), tools=[greet])
    eq = make_event_queue({"a": agent}, entry_name="a")

    events = await _run_agent("hi", agent, eq)
    tool_starts = [e for e in events if e.type == EventType.TOOL_START]
    tool_ends = [e for e in events if e.type == EventType.TOOL_END]

    assert [e.data["tool_name"] for e in tool_starts] == ["greet"]
    assert tool_ends[0].data["status"] == "success"


async def test_agent_complete_reports_cache_tokens_and_stop_reason():
    usage = {
        "inputTokens": 10,
        "outputTokens": 5,
        "totalTokens": 135,
        "cacheReadInputTokens": 100,
        "cacheWriteInputTokens": 20,
    }
    agent = Agent(model=FakeModel(["hi"], usage=usage))
    eq = make_event_queue({"a": agent}, entry_name="a")

    events = await _run_agent("hi", agent, eq)
    complete = next(e for e in events if e.type == EventType.AGENT_COMPLETE)

    assert complete.data["usage"] == {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 135,
        "cache_read_input_tokens": 100,
        "cache_write_input_tokens": 20,
    }
    assert complete.data["stop_reason"] == "end_turn"


async def test_agent_complete_cache_tokens_default_to_zero():
    agent = Agent(model=FakeModel(["hi"]))
    eq = make_event_queue({"a": agent}, entry_name="a")

    events = await _run_agent("hi", agent, eq)
    usage = next(e for e in events if e.type == EventType.AGENT_COMPLETE).data["usage"]

    assert usage["cache_read_input_tokens"] == 0
    assert usage["cache_write_input_tokens"] == 0


async def test_swarm_handoff_emits_handoff_between_the_node_events():
    first = Agent(
        name="a",
        model=ToolThenTextModel(
            tool_name="handoff_to_agent", tool_input='{"agent_name": "b", "message": "over to you"}'
        ),
    )
    second = Agent(name="b", model=FakeModel(["done"]))
    swarm = Swarm(nodes=[first, second], entry_point=first)
    eq = make_event_queue({}, orchestrators={"team": swarm}, entry_name="team")

    events = await _run_agent("go", swarm, eq)

    def _index(kind: EventType, node_id: str | None = None) -> int:
        return next(
            i
            for i, e in enumerate(events)
            if e.type == kind and (node_id is None or e.data.get("node_id") == node_id)
        )

    handoff = events[_index(EventType.HANDOFF)]
    assert handoff.data["from_node_ids"] == ["a"]
    assert handoff.data["to_node_ids"] == ["b"]
    assert handoff.data["message"] == "over to you"
    assert (
        _index(EventType.NODE_STOP, "a")
        < _index(EventType.HANDOFF)
        < _index(EventType.NODE_START, "b")
    )


async def test_node_stop_reports_status_time_and_usage():
    node = Agent(name="a", model=FakeModel(["hi"]))
    builder = GraphBuilder()
    builder.add_node(node, "a")
    builder.set_entry_point("a")
    graph = builder.build()
    eq = make_event_queue({}, orchestrators={"flow": graph}, entry_name="flow")

    events = await _run_agent("go", graph, eq)
    node_stop = next(e for e in events if e.type == EventType.NODE_STOP)

    assert node_stop.data["status"] == "completed"
    assert node_stop.data["execution_time_ms"] >= 0
    assert node_stop.data["usage"]["total_tokens"] == 8


async def test_node_stop_reports_failed_status_for_a_failing_node():
    ok = Agent(name="x", model=FakeModel(["hi"]))
    broken = Agent(name="y", model=BoomModel())
    builder = GraphBuilder()
    builder.add_node(ok, "x")
    builder.add_node(broken, "y")
    builder.add_edge("x", "y")
    builder.set_entry_point("x")
    graph = builder.build()
    eq = make_event_queue({}, orchestrators={"flow": graph}, entry_name="flow")

    events = await _run_agent("go", graph, eq)
    statuses = {
        e.data["node_id"]: e.data["status"] for e in events if e.type == EventType.NODE_STOP
    }

    assert statuses == {"x": "completed", "y": "failed"}


async def test_model_error_emits_error_and_suppresses_complete():
    agent = Agent(model=BoomModel(message="credentials expired"))
    eq = make_event_queue({"a": agent}, entry_name="a")

    events = await _run_agent("hi", agent, eq)
    kinds = [e.type for e in events]

    assert EventType.ERROR in kinds
    assert EventType.AGENT_COMPLETE not in kinds
    error = next(e for e in events if e.type == EventType.ERROR)
    assert "credentials expired" in error.data["text"]


async def test_wire_event_queue_emits_session_start_with_manifest():
    config = AppConfig(agents={"a": agent_def()}, entry="a")
    resolved = load(config)

    eq = resolved.wire_event_queue()
    first = await eq.get()

    assert first is not None
    assert first.type == EventType.SESSION_START
    assert "manifest" in first.data
