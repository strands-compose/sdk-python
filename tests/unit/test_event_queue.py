"""Tests for strands_compose.wire — EventQueue and make_event_queue."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from strands.multiagent import Swarm

from strands_compose.hooks import EventPublisher
from strands_compose.wire import EventQueue, StreamEvent, make_event_queue

# ---------------------------------------------------------------------------
# EventQueue
# ---------------------------------------------------------------------------


class TestEventQueue:
    def test_get_returns_event(self):
        async def _run():
            queue = asyncio.Queue()
            eq = EventQueue(queue)
            event = MagicMock(spec=StreamEvent)
            queue.put_nowait(event)
            return await eq.get()

        assert asyncio.run(_run()) is not None

    def test_close_then_get_returns_none(self):
        async def _run():
            queue = asyncio.Queue()
            eq = EventQueue(queue)
            await eq.close()
            return await eq.get()

        assert asyncio.run(_run()) is None

    def test_flush_clears_stale_events(self):
        queue = asyncio.Queue()
        eq = EventQueue(queue)
        for _ in range(3):
            queue.put_nowait(MagicMock(spec=StreamEvent))

        eq.flush()
        assert queue.empty()

    def test_flush_empty_queue_is_noop(self):
        eq = EventQueue(asyncio.Queue())
        eq.flush()  # should not raise


# ---------------------------------------------------------------------------
# make_event_queue
# ---------------------------------------------------------------------------


def _make_agent(name: str = "agent") -> MagicMock:
    """Return a minimal mock Agent."""
    agent = MagicMock()
    agent.agent_id = name
    agent.hooks = MagicMock()
    agent.hooks._registered_callbacks = {}
    return agent


class TestMakeEventQueue:
    def test_returns_event_queue(self):
        agent = _make_agent()
        eq = make_event_queue({"a": agent})
        assert isinstance(eq, EventQueue)

    def test_hooks_added_to_each_agent(self):
        a, b = _make_agent("a"), _make_agent("b")
        make_event_queue({"a": a, "b": b})
        assert a.hooks.add_hook.called
        assert b.hooks.add_hook.called

    def test_callback_handler_set_on_agent(self):
        agent = _make_agent()
        make_event_queue({"a": agent})
        assert agent.callback_handler is not None

    def test_wires_orchestrator(self):
        agent = _make_agent()
        orch = MagicMock(spec=Swarm)
        orch.id = "orch"
        orch.hooks = MagicMock()
        make_event_queue({"a": agent}, orchestrators={"orch": orch})
        assert orch.hooks.add_hook.called

    def test_custom_tool_labels_forwarded(self):
        agent = _make_agent()
        labels = {"a": "My Agent"}
        make_event_queue({"a": agent}, tool_labels=labels)
        # EventPublisher is constructed with our labels — check via the add_hook call arg
        pub = agent.hooks.add_hook.call_args[0][0]
        assert isinstance(pub, EventPublisher)
        assert pub._tool_labels == labels

    def test_default_label_uses_title(self):
        agent = _make_agent()
        make_event_queue({"researcher": agent})
        pub = agent.hooks.add_hook.call_args[0][0]
        assert "Researcher" in pub._tool_labels.get("researcher", "")

    @pytest.mark.asyncio
    async def test_put_event_via_wired_callback(self):
        """Verify that triggering the publisher callback enqueues an event."""
        agent = _make_agent("x")
        eq = make_event_queue({"x": agent})
        pub: EventPublisher = agent.hooks.add_hook.call_args[0][0]

        event = MagicMock(spec=StreamEvent)
        pub._callback(event)

        result = await eq.get()
        assert result is event
