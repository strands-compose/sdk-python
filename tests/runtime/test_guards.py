"""Guard hooks — behaviour observed through real strands hook events and registry.

Guards plug into strands via ``HookRegistry``; we drive them with real
``BeforeToolCallEvent`` objects (no MagicMock) and assert their observable
contract: whether the tool call is cancelled.
"""

from __future__ import annotations

import threading

import pytest
from strands import Agent, tool
from strands.hooks import HookRegistry
from strands.hooks.events import AfterModelCallEvent, BeforeToolCallEvent
from strands.types.content import Message

from strands_compose.hooks import MaxToolCallsGuard, StopGuard, ToolNameSanitizer
from tests.fakes import FakeModel


def _before_tool_event(agent: Agent, name: str, state: dict) -> BeforeToolCallEvent:
    return BeforeToolCallEvent(
        agent=agent,
        selected_tool=None,
        tool_use={"name": name, "toolUseId": "t1", "input": {}},
        invocation_state=state,
    )


def _fire(guard, event) -> BeforeToolCallEvent:
    registry = HookRegistry()
    registry.add_hook(guard)
    result, _interrupts = registry.invoke_callbacks(event)
    return result


@pytest.fixture
def agent() -> Agent:
    return Agent(model=FakeModel())


# ── MaxToolCallsGuard ──────────────────────────────────────────────────────


def test_tool_call_within_limit_is_not_cancelled(agent):
    guard = MaxToolCallsGuard(max_calls=2)
    event = _fire(guard, _before_tool_event(agent, "greet", {}))
    assert event.cancel_tool is False


def test_tool_call_over_limit_is_cancelled(agent):
    guard = MaxToolCallsGuard(max_calls=1)
    state: dict = {}
    _fire(guard, _before_tool_event(agent, "greet", state))  # call 1 — allowed
    event = _fire(guard, _before_tool_event(agent, "greet", state))  # call 2 — over limit
    assert event.cancel_tool  # truthy cancel message


def test_repeated_violation_requests_event_loop_stop(agent):
    guard = MaxToolCallsGuard(max_calls=1)
    state: dict = {}
    for _ in range(3):  # 1 allowed, 2nd warns, 3rd hard-stops
        _fire(guard, _before_tool_event(agent, "greet", state))
    assert state["request_state"]["stop_event_loop"] is True


# ── StopGuard ──────────────────────────────────────────────────────────────


def test_stop_guard_cancels_when_signal_set(agent):
    stop = threading.Event()
    stop.set()
    event = _fire(StopGuard(stop_check=stop.is_set), _before_tool_event(agent, "greet", {}))
    assert event.cancel_tool


def test_stop_guard_allows_when_signal_clear(agent):
    stop = threading.Event()
    event = _fire(StopGuard(stop_check=stop.is_set), _before_tool_event(agent, "greet", {}))
    assert event.cancel_tool is False


# ── ToolNameSanitizer ──────────────────────────────────────────────────────


@tool
def greet(name: str) -> str:
    """Greet."""
    return f"Hi {name}"


@tool
def get_weather(city: str) -> str:
    """Weather."""
    return "sunny"


@pytest.mark.parametrize(
    ("garbled", "expected"),
    [
        ("greet<|channel|>commentary", "greet"),  # prefix match on the raw name
        ("greet<|x|>", "greet"),  # trailing garbage, prefix match
        ("get<|>weather", "get_weather"),  # split on garbage, rejoin with '_'
    ],
)
def test_garbled_tool_name_is_repaired_to_a_known_tool(garbled, expected):
    agent = Agent(model=FakeModel(), tools=[greet, get_weather])
    event = _fire(ToolNameSanitizer(), _before_tool_event(agent, garbled, {}))
    assert event.tool_use["name"] == expected
    assert event.cancel_tool is False


def test_unresolvable_garbled_name_is_cancelled():
    agent = Agent(model=FakeModel(), tools=[greet])
    event = _fire(ToolNameSanitizer(), _before_tool_event(agent, "totally<|x|>bogus", {}))
    assert event.cancel_tool


def test_garbled_name_in_model_response_is_repaired_before_tool_lookup():
    # Layer 1: the sanitizer rewrites the name in the model response message
    # (via AfterModelCallEvent) before strands does its tool lookup.
    agent = Agent(model=FakeModel(), tools=[get_weather])
    message: Message = {
        "role": "assistant",
        "content": [{"toolUse": {"name": "get<|>weather", "toolUseId": "t1", "input": {}}}],
    }
    stop = AfterModelCallEvent.ModelStopResponse(stop_reason="tool_use", message=message)
    event = AfterModelCallEvent(agent=agent, invocation_state={}, stop_response=stop)

    registry = HookRegistry()
    registry.add_hook(ToolNameSanitizer())
    registry.invoke_callbacks(event)

    assert message["content"][0]["toolUse"]["name"] == "get_weather"
