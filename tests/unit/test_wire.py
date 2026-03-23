"""Tests for core.wire — StreamEvent."""

from __future__ import annotations

from strands_compose.types import EventType
from strands_compose.wire import StreamEvent


class TestStreamEvent:
    def test_asdict_serializes_timestamp(self):
        event = StreamEvent(type=EventType.TOKEN, agent_name="a")
        d = event.asdict()
        assert d["type"] == EventType.TOKEN
        assert d["agent_name"] == "a"
        assert isinstance(d["timestamp"], str)  # ISO-formatted

    def test_asdict_includes_data(self):
        event = StreamEvent(type=EventType.TOKEN, agent_name="a", data={"text": "hi"})
        assert event.asdict()["data"] == {"text": "hi"}

    def test_from_dict_round_trips_timestamp(self):
        original = StreamEvent(type=EventType.TOKEN, agent_name="a")
        restored = StreamEvent.from_dict(original.asdict())
        assert restored.timestamp == original.timestamp
        assert restored.type == original.type
        assert restored.agent_name == original.agent_name


class TestStreamEventEquality:
    def test_eq_ignores_timestamp(self):
        from datetime import datetime, timedelta, timezone

        t1 = datetime.now(tz=timezone.utc)
        t2 = t1 + timedelta(seconds=5)
        e1 = StreamEvent(type=EventType.TOKEN, agent_name="a", timestamp=t1, data={"text": "hi"})
        e2 = StreamEvent(type=EventType.TOKEN, agent_name="a", timestamp=t2, data={"text": "hi"})
        assert e1 == e2

    def test_eq_different_type_not_equal(self):
        e1 = StreamEvent(type=EventType.TOKEN, agent_name="a")
        e2 = StreamEvent(type=EventType.COMPLETE, agent_name="a")
        assert e1 != e2

    def test_eq_different_data_not_equal(self):
        e1 = StreamEvent(type=EventType.TOKEN, agent_name="a", data={"text": "x"})
        e2 = StreamEvent(type=EventType.TOKEN, agent_name="a", data={"text": "y"})
        assert e1 != e2

    def test_eq_not_stream_event(self):
        e = StreamEvent(type=EventType.TOKEN, agent_name="a")
        assert e != "not an event"
