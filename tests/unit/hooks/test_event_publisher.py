"""Tests for core.hooks.event_publisher — EventPublisher."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from strands_compose.hooks.event_publisher import (
    EventPublisher,
    _extract_result_text,
    _resolve_tool_label,
)
from strands_compose.types import EventType


class TestExtractResultText:
    def test_none_result(self):
        assert _extract_result_text(None) is None

    def test_extracts_text(self):
        result = {"content": [{"text": "hello"}]}
        assert _extract_result_text(result) == "hello"


class TestResolveToolLabel:
    def test_exact_match(self):
        assert _resolve_tool_label("query_db", {"query_db": "Query"}) == "Query"

    def test_prefix_match(self):
        assert _resolve_tool_label("query_db_v2", {"query_db": "Query"}) == "Query"

    def test_no_labels(self):
        assert _resolve_tool_label("query_db", None) is None


class TestEventPublisher:
    def test_agent_start_event(self):
        events = []
        pub = EventPublisher(callback=events.append, agent_name="test")
        agent_start_event = MagicMock()
        pub._on_agent_start(agent_start_event)

        assert len(events) == 1
        assert events[0].type == EventType.AGENT_START
        assert events[0].agent_name == "test"
        assert events[0].data == {"type": "agent"}

    def test_tool_start_and_end_events(self):
        events = []
        pub = EventPublisher(callback=events.append, agent_name="test")
        registry = MagicMock()
        pub.register_hooks(registry)

        # Simulate tool start
        tool_start_event = MagicMock()
        tool_start_event.tool_use = {"name": "greet", "toolUseId": "t1", "input": {"name": "Bob"}}
        pub._on_tool_start(tool_start_event)

        assert len(events) == 1
        assert events[0].type == EventType.TOOL_START

        # Simulate tool end
        tool_end_event = MagicMock()
        tool_end_event.tool_use = {"name": "greet", "toolUseId": "t1"}
        tool_end_event.result = {"content": [{"text": "Hello, Bob!"}]}
        tool_end_event.exception = None
        pub._on_tool_end(tool_end_event)

        assert events[1].type == EventType.TOOL_END

    def test_callback_handler_emits_tokens(self):
        events = []
        pub = EventPublisher(callback=events.append, agent_name="test")
        handler = pub.as_callback_handler()
        handler(data="Hello")

        assert len(events) == 1
        assert events[0].type == EventType.TOKEN
        assert events[0].data["text"] == "Hello"

    def test_complete_emits_with_usage(self):
        events = []
        pub = EventPublisher(callback=events.append, agent_name="test")

        # Emit complete
        complete_event = MagicMock()
        metrics = MagicMock()
        metrics.latest_agent_invocation = None
        metrics.accumulated_usage = {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}
        complete_event.agent.event_loop_metrics = metrics
        pub._on_complete(complete_event)

        assert len(events) == 1
        assert events[0].type == EventType.COMPLETE
        assert events[0].data["usage"]["input_tokens"] == 10
        assert events[0].data["usage"]["output_tokens"] == 5
        assert events[0].data["usage"]["total_tokens"] == 15


class TestHandoffEvent:
    def test_callback_handler_emits_handoff_on_multiagent_handoff_type(self) -> None:
        """as_callback_handler emits HANDOFF when type='multiagent_handoff' is received."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="orch")
        handler = pub.as_callback_handler()
        handler(type="multiagent_handoff", from_node_ids=["researcher"], to_node_ids=["analyst"])

        assert len(events) == 1
        assert events[0].type == EventType.HANDOFF

    def test_handoff_event_contains_from_and_to_node_ids(self) -> None:
        """HANDOFF event data contains from_node_ids and to_node_ids."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="orch")
        handler = pub.as_callback_handler()
        handler(
            type="multiagent_handoff",
            from_node_ids=["researcher"],
            to_node_ids=["analyst"],
            message="Need calculations",
        )

        evt = events[0]
        assert evt.data["from_node_ids"] == ["researcher"]
        assert evt.data["to_node_ids"] == ["analyst"]
        assert evt.data["message"] == "Need calculations"

    def test_handoff_event_message_none_when_absent(self) -> None:
        """HANDOFF event data message is None when not provided."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="orch")
        handler = pub.as_callback_handler()
        handler(type="multiagent_handoff", from_node_ids=["a"], to_node_ids=["b"])

        assert events[0].data["message"] is None

    def test_non_handoff_type_does_not_emit_handoff_event(self) -> None:
        """as_callback_handler does NOT emit HANDOFF for unrelated type values."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="orch")
        handler = pub.as_callback_handler()
        handler(type="node_start", node_id="researcher")

        handoff_events = [e for e in events if e.type == EventType.HANDOFF]
        assert len(handoff_events) == 0


# ---------------------------------------------------------------------------
# Model error capture (AfterModelCallEvent)
# ---------------------------------------------------------------------------


class TestModelErrorCapture:
    """EventPublisher emits ERROR events on model failures and suppresses COMPLETE."""

    def test_model_error_emits_error_event(self) -> None:
        """AfterModelCallEvent with exception emits ERROR."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="test")

        model_event = MagicMock()
        model_event.exception = RuntimeError("Token has expired")
        pub._on_model_error(model_event)

        assert len(events) == 1
        assert events[0].type == EventType.ERROR
        assert events[0].agent_name == "test"
        assert "Token has expired" in events[0].data["message"]
        assert events[0].data["exception_type"] == "RuntimeError"

    def test_model_error_sets_errored_flag(self) -> None:
        """_errored flag is set when model error occurs."""
        pub = EventPublisher(callback=lambda _: None, agent_name="test")
        assert pub._errored is False

        model_event = MagicMock()
        model_event.exception = ValueError("bad request")
        pub._on_model_error(model_event)

        assert pub._errored is True

    def test_successful_model_call_does_not_emit_error(self) -> None:
        """AfterModelCallEvent without exception emits nothing."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="test")

        model_event = MagicMock()
        model_event.exception = None
        pub._on_model_error(model_event)

        assert len(events) == 0
        assert pub._errored is False

    def test_complete_suppressed_after_error(self) -> None:
        """COMPLETE is not emitted when the invocation errored."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="test")

        # Simulate model error
        model_event = MagicMock()
        model_event.exception = RuntimeError("auth failed")
        pub._on_model_error(model_event)

        # Simulate AfterInvocationEvent (fires in finally block)
        complete_event = MagicMock()
        metrics = MagicMock()
        metrics.latest_agent_invocation = None
        metrics.accumulated_usage = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}
        complete_event.agent.event_loop_metrics = metrics
        pub._on_complete(complete_event)

        # Only the ERROR event, no COMPLETE
        assert len(events) == 1
        assert events[0].type == EventType.ERROR

    def test_complete_emitted_when_no_error(self) -> None:
        """COMPLETE is emitted normally when there was no error."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="test")

        complete_event = MagicMock()
        metrics = MagicMock()
        metrics.latest_agent_invocation = None
        metrics.accumulated_usage = {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}
        complete_event.agent.event_loop_metrics = metrics
        pub._on_complete(complete_event)

        assert len(events) == 1
        assert events[0].type == EventType.COMPLETE

    def test_errored_flag_resets_on_next_invocation(self) -> None:
        """_errored resets to False when a new invocation starts."""
        pub = EventPublisher(callback=lambda _: None, agent_name="test")

        # First invocation: error
        model_event = MagicMock()
        model_event.exception = RuntimeError("fail")
        pub._on_model_error(model_event)
        assert pub._errored is True

        # Second invocation: agent_start resets the flag
        agent_start_event = MagicMock()
        pub._on_agent_start(agent_start_event)
        assert pub._errored is False

    def test_register_hooks_includes_model_error(self) -> None:
        """register_hooks registers AfterModelCallEvent callback."""
        from strands.hooks.events import AfterModelCallEvent

        pub = EventPublisher(callback=lambda _: None, agent_name="test")
        registry = MagicMock()
        pub.register_hooks(registry)

        # Find the AfterModelCallEvent registration
        calls = registry.add_callback.call_args_list
        registered_events = [call.args[0] for call in calls]
        assert AfterModelCallEvent in registered_events


# ---------------------------------------------------------------------------
# Multiagent event handlers (R2 — coverage gap)
# ---------------------------------------------------------------------------


class TestMultiagentEvents:
    """EventPublisher emits multiagent lifecycle events (NODE_START, NODE_STOP, etc.)."""

    def test_node_start_emits_event(self) -> None:
        """_on_node_start emits NODE_START with node_id and multiagent_type."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="orchestrator")

        event = MagicMock()
        event.node_id = "researcher"
        event.source = MagicMock()
        event.source.__class__.__name__ = "Swarm"
        pub._on_node_start(event)

        assert len(events) == 1
        assert events[0].type == EventType.NODE_START
        assert events[0].agent_name == "orchestrator"
        assert events[0].data["node_id"] == "researcher"
        assert events[0].data["multiagent_type"] == "swarm"

    def test_node_stop_emits_event(self) -> None:
        """_on_node_stop emits NODE_STOP with node_id and multiagent_type."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="orchestrator")

        event = MagicMock()
        event.node_id = "analyst"
        event.source = MagicMock()
        event.source.__class__.__name__ = "Graph"
        pub._on_node_stop(event)

        assert len(events) == 1
        assert events[0].type == EventType.NODE_STOP
        assert events[0].agent_name == "orchestrator"
        assert events[0].data["node_id"] == "analyst"
        assert events[0].data["multiagent_type"] == "graph"

    def test_node_stop_uses_agent_name_not_event_node_id(self) -> None:
        """_on_node_stop uses self._agent_name as agent_name (not event.node_id)."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="my_orchestrator")

        event = MagicMock()
        event.node_id = "child_agent"
        event.source = MagicMock()
        event.source.__class__.__name__ = "Swarm"
        pub._on_node_stop(event)

        # Verify agent_name is "my_orchestrator" (not "child_agent")
        assert events[0].agent_name == "my_orchestrator"

    def test_multiagent_start_emits_event(self) -> None:
        """_on_multiagent_start emits MULTIAGENT_START with type from source class."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="pipeline")

        event = MagicMock()
        event.source = MagicMock()
        event.source.__class__.__name__ = "Swarm"
        pub._on_multiagent_start(event)

        assert len(events) == 1
        assert events[0].type == EventType.MULTIAGENT_START
        assert events[0].agent_name == "pipeline"
        assert events[0].data["multiagent_type"] == "swarm"

    def test_multiagent_complete_emits_event(self) -> None:
        """_on_multiagent_complete emits MULTIAGENT_COMPLETE."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="pipeline")

        event = MagicMock()
        event.source = MagicMock()
        event.source.__class__.__name__ = "Graph"
        pub._on_multiagent_complete(event)

        assert len(events) == 1
        assert events[0].type == EventType.MULTIAGENT_COMPLETE
        assert events[0].data["multiagent_type"] == "graph"

    def test_register_hooks_includes_all_multiagent_events(self) -> None:
        """register_hooks registers all multiagent event callbacks."""
        from strands.hooks.events import (
            AfterMultiAgentInvocationEvent,
            AfterNodeCallEvent,
            BeforeMultiAgentInvocationEvent,
            BeforeNodeCallEvent,
        )

        pub = EventPublisher(callback=lambda _: None, agent_name="test")
        registry = MagicMock()
        pub.register_hooks(registry)

        calls = registry.add_callback.call_args_list
        registered_events = [call.args[0] for call in calls]
        assert BeforeNodeCallEvent in registered_events
        assert AfterNodeCallEvent in registered_events
        assert BeforeMultiAgentInvocationEvent in registered_events
        assert AfterMultiAgentInvocationEvent in registered_events

    def test_full_multiagent_lifecycle_sequence(self) -> None:
        """Full lifecycle: multiagent_start -> node_start -> node_stop -> multiagent_complete."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="orch")

        # Simulate full lifecycle
        source = MagicMock()
        source.__class__.__name__ = "Swarm"

        ma_start = MagicMock()
        ma_start.source = source
        pub._on_multiagent_start(ma_start)

        node_start = MagicMock()
        node_start.node_id = "agent_a"
        node_start.source = source
        pub._on_node_start(node_start)

        node_stop = MagicMock()
        node_stop.node_id = "agent_a"
        node_stop.source = source
        pub._on_node_stop(node_stop)

        ma_complete = MagicMock()
        ma_complete.source = source
        pub._on_multiagent_complete(ma_complete)

        assert len(events) == 4
        assert events[0].type == EventType.MULTIAGENT_START
        assert events[1].type == EventType.NODE_START
        assert events[2].type == EventType.NODE_STOP
        assert events[3].type == EventType.MULTIAGENT_COMPLETE


# ---------------------------------------------------------------------------
# Callback handler reasoning events
# ---------------------------------------------------------------------------


class TestCallbackHandlerReasoningEvents:
    """as_callback_handler emits REASONING events for reasoningText kwarg."""

    def test_reasoning_text_emits_reasoning_event(self) -> None:
        """reasoningText kwarg produces a REASONING event."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="test")
        handler = pub.as_callback_handler()
        handler(reasoningText="Let me think about this...")

        assert len(events) == 1
        assert events[0].type == EventType.REASONING
        assert events[0].data["text"] == "Let me think about this..."

    def test_empty_reasoning_text_does_not_emit(self) -> None:
        """Empty reasoningText string does not produce an event."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="test")
        handler = pub.as_callback_handler()
        handler(reasoningText="")

        assert len(events) == 0

    def test_data_and_reasoning_both_emit(self) -> None:
        """Both data and reasoningText in same call emit TOKEN + REASONING."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="test")
        handler = pub.as_callback_handler()
        handler(data="answer", reasoningText="thought")

        types = [e.type for e in events]
        assert EventType.TOKEN in types
        assert EventType.REASONING in types


# ---------------------------------------------------------------------------
# _safe_callback wrapper
# ---------------------------------------------------------------------------


class TestSafeCallbackWrapper:
    """_safe_callback wraps callbacks to log exceptions instead of propagating."""

    def test_runtime_error_is_swallowed(self) -> None:
        """RuntimeError in callback is logged, not propagated."""

        def _failing_cb(event):
            raise RuntimeError("connection lost")

        pub = EventPublisher(callback=_failing_cb, agent_name="test")
        # Should not raise
        pub._callback(MagicMock())

    def test_os_error_is_swallowed(self) -> None:
        """OSError in callback is logged, not propagated."""

        def _failing_cb(event):
            raise OSError("broken pipe")

        pub = EventPublisher(callback=_failing_cb, agent_name="test")
        pub._callback(MagicMock())

    def test_unexpected_exception_is_reraised(self) -> None:
        """Non-expected exceptions are logged and re-raised."""

        def _failing_cb(event):
            raise TypeError("unexpected")

        pub = EventPublisher(callback=_failing_cb, agent_name="test")
        with pytest.raises(TypeError, match="unexpected"):
            pub._callback(MagicMock())


# ---------------------------------------------------------------------------
# _extract_result_text edge cases
# ---------------------------------------------------------------------------


class TestExtractResultTextEdgeCases:
    """Additional edge cases for _extract_result_text."""

    def test_json_block_extracted(self) -> None:
        """JSON blocks in content are extracted as text."""
        result = {"content": [{"json": {"key": "value"}}]}
        text = _extract_result_text(result)
        assert text is not None
        assert "key" in text
        assert "value" in text

    def test_long_text_truncated(self) -> None:
        """Text longer than max_len is truncated with '...'."""
        long_text = "x" * 700
        result = {"content": [{"text": long_text}]}
        text = _extract_result_text(result, max_len=100)
        assert text is not None
        assert len(text) == 103  # 100 + "..."
        assert text.endswith("...")

    def test_empty_content_returns_none(self) -> None:
        """Empty content list returns None."""
        result = {"content": []}
        assert _extract_result_text(result) is None
