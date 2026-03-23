"""Tests for core.hooks.stop_guard — StopGuard, MultiAgentStopGuard, stop_guard_from_event."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from strands_compose.hooks.stop_guard import (
    MultiAgentStopGuard,
    StopGuard,
    stop_guard_from_event,
)


class TestStopGuard:
    def test_no_cancel_when_check_false(self, make_before_tool_event):
        guard = StopGuard(stop_check=lambda: False)
        event = make_before_tool_event()
        guard._on_before_tool(event)
        assert event.cancel_tool is False

    def test_cancels_when_check_true(self, make_before_tool_event):
        guard = StopGuard(stop_check=lambda: True)
        event = make_before_tool_event()
        guard._on_before_tool(event)
        assert event.cancel_tool == "Agent stopped by external signal"

    def test_sets_stop_event_loop_on_cancel(self, make_before_tool_event):
        """When stop is triggered, request_state.stop_event_loop is set."""
        guard = StopGuard(stop_check=lambda: True)
        event = make_before_tool_event()
        guard._on_before_tool(event)
        assert event.invocation_state["request_state"]["stop_event_loop"] is True

    def test_register_hooks_registers_before_tool(self):
        """register_hooks registers BeforeToolCallEvent callback."""
        from strands.hooks.events import BeforeToolCallEvent

        guard = StopGuard(stop_check=lambda: False)
        registry = MagicMock()
        guard.register_hooks(registry)

        calls = registry.add_callback.call_args_list
        registered_events = [call.args[0] for call in calls]
        assert BeforeToolCallEvent in registered_events


class TestStopGuardFromEvent:
    def test_creates_guard_and_event(self):
        guard, event = stop_guard_from_event()
        assert isinstance(guard, StopGuard)
        assert isinstance(event, threading.Event)

    def test_trigger_via_event(self, make_before_tool_event):
        guard, stop = stop_guard_from_event()
        event = make_before_tool_event()

        guard._on_before_tool(event)
        assert event.cancel_tool is False

        stop.set()
        event2 = make_before_tool_event()
        guard._on_before_tool(event2)
        assert event2.cancel_tool == "Agent stopped by external signal"

    def test_accepts_existing_event(self):
        """stop_guard_from_event accepts a pre-existing threading.Event."""
        existing = threading.Event()
        guard, event = stop_guard_from_event(event=existing)
        assert event is existing


class TestMultiAgentStopGuard:
    """Tests for MultiAgentStopGuard (R3 — coverage gap)."""

    def test_no_cancel_when_check_false(self) -> None:
        """Node is not cancelled when stop check returns False."""
        guard = MultiAgentStopGuard(stop_check=lambda: False)
        event = MagicMock()
        event.cancel_node = False
        guard._on_before_node(event)
        assert event.cancel_node is False

    def test_cancels_node_when_check_true(self) -> None:
        """Node is cancelled when stop check returns True."""
        guard = MultiAgentStopGuard(stop_check=lambda: True)
        event = MagicMock()
        event.cancel_node = False
        guard._on_before_node(event)
        assert event.cancel_node == "stop requested"

    def test_register_hooks_registers_before_node(self) -> None:
        """register_hooks registers BeforeNodeCallEvent callback."""
        from strands.hooks.events import BeforeNodeCallEvent

        guard = MultiAgentStopGuard(stop_check=lambda: False)
        registry = MagicMock()
        guard.register_hooks(registry)

        calls = registry.add_callback.call_args_list
        registered_events = [call.args[0] for call in calls]
        assert BeforeNodeCallEvent in registered_events

    def test_dynamic_stop_check(self) -> None:
        """Guard responds to dynamic changes in stop_check return value."""
        flag = threading.Event()
        guard = MultiAgentStopGuard(stop_check=flag.is_set)

        event1 = MagicMock()
        event1.cancel_node = False
        guard._on_before_node(event1)
        assert event1.cancel_node is False

        flag.set()

        event2 = MagicMock()
        event2.cancel_node = False
        guard._on_before_node(event2)
        assert event2.cancel_node == "stop requested"
