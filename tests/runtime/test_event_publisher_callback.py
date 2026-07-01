"""EventPublisher's public callback-handler seam — TOKEN / REASONING / HANDOFF.

``as_callback_handler`` is public API (a strands-compatible callback_handler).
We drive it directly and observe the emitted StreamEvents — no private handlers.
"""

from __future__ import annotations

from strands_compose.hooks import EventPublisher
from strands_compose.types import EventType


def _publisher() -> tuple[EventPublisher, list]:
    events: list = []
    return EventPublisher(callback=events.append, agent_name="a"), events


def test_data_chunk_emits_token_event():
    pub, events = _publisher()
    pub.as_callback_handler()(data="hello")
    assert events[0].type == EventType.TOKEN
    assert events[0].data["text"] == "hello"


def test_reasoning_chunk_emits_reasoning_event():
    pub, events = _publisher()
    pub.as_callback_handler()(reasoningText="thinking")
    assert events[0].type == EventType.REASONING
    assert events[0].data["text"] == "thinking"


def test_empty_chunk_emits_nothing():
    pub, events = _publisher()
    pub.as_callback_handler()(data="")
    assert events == []


def test_multiagent_handoff_emits_handoff_event():
    pub, events = _publisher()
    pub.as_callback_handler()(
        type="multiagent_handoff", from_node_ids=["r"], to_node_ids=["w"], message="over to you"
    )
    assert events[0].type == EventType.HANDOFF
    assert events[0].data["to_node_ids"] == ["w"]
    assert events[0].data["message"] == "over to you"


def test_callback_exception_is_swallowed_not_propagated():
    def _boom(_event):
        raise RuntimeError("consumer disconnected")

    pub = EventPublisher(callback=_boom, agent_name="a")
    # A RuntimeError in the consumer must not crash the producer.
    pub.as_callback_handler()(data="hi")
