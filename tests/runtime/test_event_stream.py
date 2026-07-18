"""StreamEvent translation through the real event loop + make_event_queue.

Drives real strands agents with FakeModels — the highest-fidelity way to prove
EventPublisher's translation without touching its private handlers.
"""

from __future__ import annotations

import asyncio

from strands import Agent, tool

from strands_compose.config import load_session, resolve_infra
from strands_compose.config.schema import AppConfig
from strands_compose.types import EventType
from strands_compose.wire import make_event_queue
from tests.factories import agent_def
from tests.fakes import BoomModel, FakeModel, ToolThenTextModel


async def _drain(eq) -> list:
    events = []
    while True:
        ev = await eq.get()
        if ev is None:
            break
        events.append(ev)
    return events


async def _run_agent(prompt: str, agent: Agent, eq) -> list:
    async def _invoke() -> None:
        try:
            await agent.invoke_async(prompt)
        except Exception:  # noqa: BLE001 — error path is asserted via events
            pass
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


async def test_agent_complete_includes_model_id_and_provider():
    agent = Agent(model=FakeModel(["hi"], model_id="us.anthropic.claude-sonnet-4-6"))
    eq = make_event_queue({"a": agent}, entry_name="a")

    events = await _run_agent("hi", agent, eq)
    complete = next(e for e in events if e.type == EventType.AGENT_COMPLETE)

    assert complete.data["model"]["model_id"] == "us.anthropic.claude-sonnet-4-6"
    assert complete.data["model"]["provider"] == f"{FakeModel.__module__}.{FakeModel.__qualname__}"


async def test_stream_is_bracketed_by_session_end():
    agent = Agent(model=FakeModel(["hi"]))
    eq = make_event_queue({"a": agent}, entry_name="a")
    events = await _run_agent("hi", agent, eq)
    assert events[-1].type == EventType.SESSION_END


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
    resolved = load_session(config, resolve_infra(config))

    eq = resolved.wire_event_queue()
    first = await eq.get()

    assert first is not None
    assert first.type == EventType.SESSION_START
    assert "manifest" in first.data
