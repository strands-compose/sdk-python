"""EventQueue behaviour — session bracketing, sentinel hiding, flush, overflow."""

from __future__ import annotations

import asyncio
import threading

from strands_compose.types import EventType, StreamEvent
from strands_compose.wire import EventQueue


def _event(text: str = "hi") -> StreamEvent:
    return StreamEvent(type=EventType.TOKEN, agent_name="a", data={"text": text})


async def test_close_emits_session_end_then_stops_the_stream():
    eq = EventQueue(asyncio.Queue(), entry_name="a")
    await eq.close()

    first = await eq.get()
    assert first is not None
    assert first.type == EventType.SESSION_END
    assert await eq.get() is None  # sentinel surfaces as None


async def test_put_event_is_delivered_to_consumer():
    eq = EventQueue(asyncio.Queue())
    event = _event()
    eq.put_event(event)
    assert await eq.get() is event


async def test_flush_discards_pending_events():
    eq = EventQueue(asyncio.Queue())
    for _ in range(5):
        eq.put_event(_event())
    eq.flush()
    eq.put_event(_event("after"))
    got = await eq.get()
    assert got is not None
    assert got.data["text"] == "after"


async def test_full_queue_drops_events_without_raising():
    eq = EventQueue(asyncio.Queue(maxsize=1))
    eq.put_event(_event("kept"))
    eq.put_event(_event("dropped"))  # must not raise
    got = await eq.get()
    assert got is not None
    assert got.data["text"] == "kept"


async def test_events_from_background_threads_are_delivered():
    eq = EventQueue(asyncio.Queue(maxsize=100))
    total = 20

    def _produce() -> None:
        for _ in range(total):
            eq.put_event(_event())

    threads = [threading.Thread(target=_produce) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    await eq.close()

    received = []
    while True:
        ev = await eq.get()
        if ev is None:
            break
        received.append(ev)
    # No events dropped under concurrency (3 producers × 20 tokens each)...
    tokens = [e for e in received if e.type == EventType.TOKEN]
    assert len(tokens) == total * 3
    # ...and the stream is still bracketed by a single SESSION_END.
    assert received[-1].type == EventType.SESSION_END
