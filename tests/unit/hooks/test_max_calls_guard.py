"""Tests for core.hooks.max_calls_guard — MaxToolCallsGuard."""

from __future__ import annotations

import logging

from strands_compose.hooks.max_calls_guard import MaxToolCallsGuard


class TestMaxToolCallsGuard:
    def test_allows_calls_under_limit(self, make_before_tool_event):
        guard = MaxToolCallsGuard(max_calls=3)
        event = make_before_tool_event()
        for _ in range(3):
            guard._on_before_tool(event)
        assert event.cancel_tool is False

    def test_graceful_on_first_over_limit(self, make_before_tool_event, caplog):
        """First violation: cancel the tool, warn, but do NOT stop the event loop."""
        guard = MaxToolCallsGuard(max_calls=2)
        event = make_before_tool_event()
        guard._on_before_tool(event)  # 1
        guard._on_before_tool(event)  # 2
        with caplog.at_level(logging.WARNING, logger="strands_compose.hooks.max_calls_guard"):
            guard._on_before_tool(event)  # 3 — first violation

        assert event.cancel_tool  # tool was cancelled
        assert "Do not call any more tools" in str(event.cancel_tool)
        assert event.invocation_state.get("max_tool_calls_guard_limit_hit") is True
        # stop_event_loop must NOT be set on the first violation
        assert not event.invocation_state.get("request_state", {}).get("stop_event_loop", False)
        assert any("tool call limit reached" in m for m in caplog.messages)

    def test_hard_stop_on_second_over_limit(self, make_before_tool_event, caplog):
        """Second violation: LLM ignored the warning — hard stop."""
        guard = MaxToolCallsGuard(max_calls=2)
        event = make_before_tool_event()
        guard._on_before_tool(event)  # 1
        guard._on_before_tool(event)  # 2
        guard._on_before_tool(event)  # 3 — graceful
        with caplog.at_level(logging.WARNING, logger="strands_compose.hooks.max_calls_guard"):
            guard._on_before_tool(event)  # 4 — hard stop

        assert event.cancel_tool
        assert event.invocation_state.get("request_state", {}).get("stop_event_loop") is True
        assert any("ignored tool call limit" in m for m in caplog.messages)
