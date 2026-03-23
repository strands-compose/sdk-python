"""Tests for RawStreamConverter and StreamEvent.from_dict()."""

from __future__ import annotations

import pytest

from strands_compose.converters.raw import RawStreamConverter
from strands_compose.wire import StreamEvent

AGENT = "test-agent"


def _event(type_: str, **data: object) -> StreamEvent:
    """Build a StreamEvent with the given type and payload."""
    return StreamEvent(type=type_, agent_name=AGENT, data=dict(data))


class TestRawStreamConverter:
    """RawStreamConverter behaviour tests."""

    def test_convert_returns_event_asdict(self) -> None:
        """convert() returns a single-element list with the event's asdict()."""
        conv = RawStreamConverter()
        event = _event("token", text="hello")
        result = conv.convert(event)

        assert result == [event.asdict()]

    def test_convert_returns_list_with_single_element(self) -> None:
        """convert() always returns a list of length 1."""
        conv = RawStreamConverter()
        event = _event("complete")
        result = conv.convert(event)

        assert isinstance(result, list)
        assert len(result) == 1

    def test_done_marker_returns_empty_string(self) -> None:
        """done_marker() returns an empty string."""
        conv = RawStreamConverter()
        assert conv.done_marker() == ""

    def test_convert_preserves_payload_fields(self) -> None:
        """convert() preserves type, agent_name, and data in the output dict."""
        conv = RawStreamConverter()
        event = _event("tool_start", tool_name="calculator", tool_input={"x": 1})
        result = conv.convert(event)

        chunk = result[0]
        assert chunk["type"] == "tool_start"
        assert chunk["agent_name"] == AGENT
        assert chunk["data"]["tool_name"] == "calculator"

    @pytest.mark.parametrize(
        "event_type",
        ["token", "reasoning", "tool_start", "tool_end", "complete", "error"],
    )
    def test_convert_works_for_all_event_types(self, event_type: str) -> None:
        """convert() handles any event type without raising."""
        conv = RawStreamConverter()
        event = _event(event_type)
        result = conv.convert(event)

        assert len(result) == 1
        assert result[0]["type"] == event_type


class TestStreamEventFromDict:
    """StreamEvent.from_dict() round-trip and partial-dict tests."""

    def test_round_trip(self) -> None:
        """from_dict(event.asdict()) reproduces the original event fields."""
        original = _event("token", text="world")
        restored = StreamEvent.from_dict(original.asdict())

        assert restored.type == original.type
        assert restored.agent_name == original.agent_name
        assert restored.data == original.data

    def test_round_trip_preserves_timestamp(self) -> None:
        """from_dict(event.asdict()) faithfully restores the original timestamp."""
        original = _event("token", text="hello")
        restored = StreamEvent.from_dict(original.asdict())

        assert restored.timestamp == original.timestamp

    def test_from_dict_with_only_type_field(self) -> None:
        """from_dict() works when only 'type' is present; optional fields default."""
        event = StreamEvent.from_dict({"type": "token", "data": {"text": "hi"}})

        assert event.type == "token"
        assert event.agent_name == ""
        assert event.data == {"text": "hi"}

    def test_from_dict_missing_optional_fields_uses_defaults(self) -> None:
        """from_dict() sets agent_name='' and data={} when those keys are absent."""
        event = StreamEvent.from_dict({"type": "complete"})

        assert event.type == "complete"
        assert event.agent_name == ""
        assert event.data == {}

    def test_from_dict_defaults_type_when_missing(self) -> None:
        """from_dict() defaults type to '' when 'type' is absent."""
        event = StreamEvent.from_dict({"agent_name": "foo"})
        assert event.type == ""
        assert event.agent_name == "foo"

    def test_from_dict_accepts_datetime_timestamp(self) -> None:
        """from_dict() accepts a datetime object for timestamp (no parse needed)."""
        from datetime import datetime, timezone

        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        event = StreamEvent.from_dict({"type": "token", "timestamp": ts})
        assert event.timestamp == ts

    def test_from_dict_defaults_timestamp_on_non_string(self) -> None:
        """from_dict() uses now() when timestamp is a non-string, non-datetime."""
        from datetime import datetime

        event = StreamEvent.from_dict({"type": "token", "timestamp": 12345})
        assert isinstance(event.timestamp, datetime)

    def test_from_dict_empty_dict(self) -> None:
        """from_dict({}) returns a StreamEvent with all defaults."""
        event = StreamEvent.from_dict({})
        assert event.type == ""
        assert event.agent_name == ""
        assert event.data == {}
