"""Concurrent access tests for EventQueue and MCPLifecycle (R6).

Validates thread-safety and async behavior under concurrent load.
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from strands_compose.mcp.lifecycle import MCPLifecycle
from strands_compose.wire import EventQueue, StreamEvent

# ---------------------------------------------------------------------------
# EventQueue concurrency tests
# ---------------------------------------------------------------------------


class TestEventQueueConcurrency:
    """Validate EventQueue under concurrent access patterns."""

    @pytest.mark.asyncio
    async def test_multiple_producers_single_consumer(self) -> None:
        """Multiple threads can put events while one async consumer reads them."""
        queue = asyncio.Queue(maxsize=100)
        eq = EventQueue(queue)
        num_events = 50
        received: list[StreamEvent] = []

        def _producer(start: int, count: int) -> None:
            """Put events from a background thread using put_event (thread-safe)."""
            for i in range(count):
                event = StreamEvent(
                    type="token",
                    agent_name=f"producer-{start}",
                    data={"index": start + i},
                )
                eq.put_event(event)

        threads = []
        for t_idx in range(5):
            t = threading.Thread(target=_producer, args=(t_idx * 10, 10))
            threads.append(t)

        # Start all producers
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Signal end
        await eq.close()

        # Consume
        while True:
            event = await eq.get()
            if event is None:
                break
            received.append(event)

        assert len(received) == num_events

    @pytest.mark.asyncio
    async def test_put_event_thread_safe(self) -> None:
        """put_event can be called from threads safely."""
        queue = asyncio.Queue(maxsize=100)
        eq = EventQueue(queue)
        event = StreamEvent(type="token", agent_name="test", data={"text": "hi"})

        eq.put_event(event)
        result = await eq.get()
        assert result is event

    @pytest.mark.asyncio
    async def test_queue_full_drops_event(self) -> None:
        """When queue is full, events are dropped with a warning (not raised)."""
        queue = asyncio.Queue(maxsize=1)
        eq = EventQueue(queue)

        # Fill the queue
        event1 = StreamEvent(type="token", agent_name="a", data={})
        event2 = StreamEvent(type="token", agent_name="a", data={})
        eq._put(event1)
        eq._put(event2)  # Should be dropped, not raise

        result = await eq.get()
        assert result is event1

    @pytest.mark.asyncio
    async def test_close_then_get_returns_none(self) -> None:
        """Closing the queue causes get to return None."""
        queue = asyncio.Queue()
        eq = EventQueue(queue)
        await eq.close()
        result = await eq.get()
        assert result is None

    @pytest.mark.asyncio
    async def test_flush_during_production(self) -> None:
        """flush() clears all pending events."""
        queue = asyncio.Queue(maxsize=100)
        eq = EventQueue(queue)

        for i in range(10):
            eq._put(StreamEvent(type="token", agent_name="a", data={"i": i}))

        eq.flush()
        assert queue.empty()


# ---------------------------------------------------------------------------
# MCPLifecycle concurrency tests
# ---------------------------------------------------------------------------


class TestMCPLifecycleConcurrency:
    """Validate MCPLifecycle thread-safety and idempotent operations."""

    def test_concurrent_start_is_idempotent(self) -> None:
        """Calling start() from multiple threads results in only one server.start()."""
        lc = MCPLifecycle()
        server = MagicMock()
        server.wait_ready.return_value = True
        lc.add_server("s", server)

        threads = []
        for _ in range(5):
            t = threading.Thread(target=lc.start)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Server.start should only be called once due to idempotency
        server.start.assert_called_once()

    def test_stop_after_start_from_different_thread(self) -> None:
        """start() in one thread, stop() in another — no deadlocks."""
        lc = MCPLifecycle()
        server = MagicMock()
        server.wait_ready.return_value = True
        lc.add_server("s", server)

        lc.start()

        stop_thread = threading.Thread(target=lc.stop)
        stop_thread.start()
        stop_thread.join(timeout=5)

        assert not stop_thread.is_alive(), "stop() should complete without deadlock"
        assert not lc._started

    def test_concurrent_stop_is_safe(self) -> None:
        """Multiple stop() calls from different threads don't raise."""
        lc = MCPLifecycle()
        server = MagicMock()
        server.wait_ready.return_value = True
        lc.add_server("s", server)
        lc.start()

        threads = []
        for _ in range(5):
            t = threading.Thread(target=lc.stop)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not lc._started
