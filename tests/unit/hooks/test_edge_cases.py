"""Edge-case tests for modules identified as under-tested in FINAL_REVIEW §7.4."""

from __future__ import annotations

import logging

from strands_compose.hooks.max_calls_guard import MaxToolCallsGuard


class TestMaxToolCallsGuardEdgeCases:
    """Edge cases for MaxToolCallsGuard (FINAL_REVIEW §7.4)."""

    def test_max_calls_one_allows_single_call(self, make_before_tool_event):
        """max_calls=1 should allow exactly one tool call."""
        guard = MaxToolCallsGuard(max_calls=1)
        event = make_before_tool_event()
        guard._on_before_tool(event)  # call 1 — should be allowed
        assert event.cancel_tool is False

    def test_max_calls_one_triggers_on_second(self, make_before_tool_event):
        """max_calls=1 should trigger graceful stop on second call."""
        guard = MaxToolCallsGuard(max_calls=1)
        event = make_before_tool_event()
        guard._on_before_tool(event)  # 1 — allowed
        guard._on_before_tool(event)  # 2 — first violation
        assert event.cancel_tool  # graceful: cancelled but no hard stop
        assert not event.invocation_state.get("request_state", {}).get("stop_event_loop", False)

    def test_max_calls_zero_triggers_on_first(self, make_before_tool_event):
        """max_calls=0 should trigger on the very first tool call (degenerate case)."""
        guard = MaxToolCallsGuard(max_calls=0)
        event = make_before_tool_event()
        guard._on_before_tool(event)  # 1 — exceeds 0
        assert event.cancel_tool

    def test_default_max_calls_is_25(self):
        """Default guard allows 25 calls."""
        guard = MaxToolCallsGuard()
        assert guard.max_calls == 25

    def test_separate_invocation_states_are_independent(self, make_before_tool_event):
        """Different invocation_state dicts should track independently."""
        guard = MaxToolCallsGuard(max_calls=1)
        event1 = make_before_tool_event(invocation_state={})
        event2 = make_before_tool_event(invocation_state={})
        guard._on_before_tool(event1)  # event1: call 1 — OK
        guard._on_before_tool(event2)  # event2: call 1 — also OK
        assert event1.cancel_tool is False
        assert event2.cancel_tool is False

    def test_graceful_then_hard_with_max_one(self, make_before_tool_event, caplog):
        """With max_calls=1: call 2 = graceful, call 3 = hard stop."""
        guard = MaxToolCallsGuard(max_calls=1)
        event = make_before_tool_event()
        guard._on_before_tool(event)  # 1 — allowed
        guard._on_before_tool(event)  # 2 — graceful
        with caplog.at_level(logging.WARNING):
            guard._on_before_tool(event)  # 3 — hard stop
        assert event.invocation_state.get("request_state", {}).get("stop_event_loop") is True
