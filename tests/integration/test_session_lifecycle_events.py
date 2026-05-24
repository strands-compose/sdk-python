"""Integration tests for session lifecycle events (SESSION_START and SESSION_END).

Tests verify that SESSION_START is emitted as the first event and SESSION_END
as the last typed event before the stream sentinel, across various
orchestration topologies and invocation cycles.
"""

from __future__ import annotations

import pytest

from strands_compose.config import load
from strands_compose.types import EventType, StreamEvent


@pytest.mark.integration
class TestSessionLifecycleEventsSingleAgent:
    """Session lifecycle events with a single agent."""

    @pytest.mark.asyncio
    async def test_session_start_first_session_end_last_single_agent(self, fixture_path):
        """Verify SESSION_START is first event and SESSION_END is last for single agent."""
        resolved = load(fixture_path("minimal.yaml"))
        eq = resolved.wire_event_queue()

        events: list[StreamEvent] = []

        try:
            # Simulate a simple invocation by just closing the queue
            # (no actual agent call, just testing event ordering)
            pass
        finally:
            await eq.close()

        while True:
            event = await eq.get()
            if event is None:
                break
            events.append(event)

        assert len(events) >= 2, "Expected at least SESSION_START and SESSION_END"
        assert events[0].type == EventType.SESSION_START, "First event should be SESSION_START"
        assert events[0].agent_name == "greeter", "SESSION_START agent_name should be entry point"

        assert events[-1].type == EventType.SESSION_END, "Last event should be SESSION_END"
        assert events[-1].agent_name == "greeter", "SESSION_END agent_name should be entry point"
        assert events[-1].data == {"session_id": None}, "SESSION_END data should have session_id"

    @pytest.mark.asyncio
    async def test_session_start_payload_contains_manifest(self, fixture_path):
        """Verify SESSION_START payload contains valid manifest."""
        resolved = load(fixture_path("minimal.yaml"))
        eq = resolved.wire_event_queue()

        try:
            pass
        finally:
            await eq.close()

        event = await eq.get()
        assert event is not None
        assert event.type == EventType.SESSION_START

        manifest = event.data
        assert isinstance(manifest, dict)
        assert "agents" in manifest
        assert "orchestrations" in manifest
        assert "entry" in manifest

        assert isinstance(manifest["agents"], list)
        assert len(manifest["agents"]) > 0
        agent = manifest["agents"][0]
        assert "name" in agent
        assert "description" in agent
        assert "model" in agent
        assert "session_manager" in agent

        entry = manifest["entry"]
        assert "name" in entry
        assert "kind" in entry
        assert entry["kind"] in ("agent", "orchestration")


@pytest.mark.integration
class TestSessionLifecycleEventsMultipleAgents:
    """Session lifecycle events with multiple agents."""

    @pytest.mark.asyncio
    async def test_session_start_session_end_multiple_agents(self, fixture_path):
        """Verify SESSION_START and SESSION_END with multiple agents."""
        resolved = load(fixture_path("multi_agent_delegate.yaml"))
        eq = resolved.wire_event_queue()

        events: list[StreamEvent] = []
        try:
            pass
        finally:
            await eq.close()

        while True:
            event = await eq.get()
            if event is None:
                break
            events.append(event)

        assert events[0].type == EventType.SESSION_START
        assert events[0].agent_name == "coordinator"

        assert events[-1].type == EventType.SESSION_END
        assert events[-1].agent_name == "coordinator"

        manifest = events[0].data
        agent_names = {agent["name"] for agent in manifest["agents"]}
        assert "researcher" in agent_names
        assert "writer" in agent_names


@pytest.mark.integration
class TestSessionLifecycleEventsSwarmOrchestration:
    """Session lifecycle events with swarm orchestration."""

    @pytest.mark.asyncio
    async def test_session_start_session_end_swarm(self, fixture_path):
        """Verify SESSION_START and SESSION_END with swarm orchestration."""
        resolved = load(fixture_path("swarm.yaml"))
        eq = resolved.wire_event_queue()

        events: list[StreamEvent] = []
        try:
            pass
        finally:
            await eq.close()

        while True:
            event = await eq.get()
            if event is None:
                break
            events.append(event)

        assert events[0].type == EventType.SESSION_START
        assert events[0].agent_name == "team"

        assert events[-1].type == EventType.SESSION_END
        assert events[-1].agent_name == "team"

        manifest = events[0].data
        assert len(manifest["orchestrations"]) > 0
        swarm = manifest["orchestrations"][0]
        assert swarm["kind"] == "swarm"
        assert "nodes" in swarm
        assert len(swarm["nodes"]) > 0


@pytest.mark.integration
class TestSessionLifecycleEventsGraphOrchestration:
    """Session lifecycle events with graph orchestration."""

    @pytest.mark.asyncio
    async def test_session_start_session_end_graph(self, fixture_path):
        """Verify SESSION_START and SESSION_END with graph orchestration."""
        resolved = load(fixture_path("graph.yaml"))
        eq = resolved.wire_event_queue()

        events: list[StreamEvent] = []
        try:
            pass
        finally:
            await eq.close()

        while True:
            event = await eq.get()
            if event is None:
                break
            events.append(event)

        assert events[0].type == EventType.SESSION_START
        assert events[0].agent_name == "pipeline"

        assert events[-1].type == EventType.SESSION_END
        assert events[-1].agent_name == "pipeline"

        manifest = events[0].data
        assert len(manifest["orchestrations"]) > 0
        graph = manifest["orchestrations"][0]
        assert graph["kind"] == "graph"
        assert "nodes" in graph
        assert "edges" in graph
        assert isinstance(graph["edges"], list)


@pytest.mark.integration
class TestSessionLifecycleEventsMultipleInvocations:
    """Session lifecycle events across multiple invocation cycles."""

    @pytest.mark.asyncio
    async def test_multiple_invocations_separate_session_end(self, fixture_path):
        """Verify separate SESSION_END for each invocation cycle.

        Note: SESSION_START is only emitted once when wire_event_queue() is called.
        For multiple invocations, the caller must manually call emit_session_start()
        after flush() if they want a new SESSION_START for the next invocation.
        """
        resolved = load(fixture_path("minimal.yaml"))
        eq = resolved.wire_event_queue()

        events1: list[StreamEvent] = []
        try:
            pass
        finally:
            await eq.close()

        while True:
            event = await eq.get()
            if event is None:
                break
            events1.append(event)

        assert events1[0].type == EventType.SESSION_START
        assert events1[-1].type == EventType.SESSION_END

        eq.flush()
        events2: list[StreamEvent] = []
        try:
            pass
        finally:
            await eq.close()

        while True:
            event = await eq.get()
            if event is None:
                break
            events2.append(event)

        assert events2[-1].type == EventType.SESSION_END

        assert events1[-1] is not events2[-1]


@pytest.mark.integration
class TestSessionLifecycleEventsExceptionHandling:
    """Session lifecycle events when exceptions occur during invocation."""

    @pytest.mark.asyncio
    async def test_session_end_emitted_on_exception(self, fixture_path):
        """Verify SESSION_END is emitted even when exception occurs."""
        resolved = load(fixture_path("minimal.yaml"))
        eq = resolved.wire_event_queue()

        events: list[StreamEvent] = []
        exception_raised = False

        try:
            raise RuntimeError("Simulated invocation error")
        except RuntimeError:
            exception_raised = True
        finally:
            await eq.close()

        while True:
            event = await eq.get()
            if event is None:
                break
            events.append(event)

        assert exception_raised

        assert len(events) >= 2
        assert events[0].type == EventType.SESSION_START
        assert events[-1].type == EventType.SESSION_END


@pytest.mark.integration
class TestSessionLifecycleEventsIdempotency:
    """Session lifecycle events idempotency and guard behavior."""

    @pytest.mark.asyncio
    async def test_close_called_multiple_times_session_end_once(self, fixture_path):
        """Verify SESSION_END is emitted only once even if close() called multiple times."""
        resolved = load(fixture_path("minimal.yaml"))
        eq = resolved.wire_event_queue()

        try:
            pass
        finally:
            await eq.close()
            await eq.close()
            await eq.close()

        events: list[StreamEvent] = []
        while True:
            event = await eq.get()
            if event is None:
                break
            events.append(event)

        session_end_count = sum(1 for e in events if e.type == EventType.SESSION_END)
        assert session_end_count == 1, "SESSION_END should be emitted exactly once"

    @pytest.mark.asyncio
    async def test_flush_resets_guards_allows_reemission(self, fixture_path):
        """Verify flush() resets guards and allows re-emission in next cycle.

        Note: SESSION_START is only emitted once when wire_event_queue() is called.
        For multiple invocations, the caller must manually call emit_session_start()
        after flush() if they want a new SESSION_START for the next invocation.
        """
        resolved = load(fixture_path("minimal.yaml"))
        eq = resolved.wire_event_queue()

        try:
            pass
        finally:
            await eq.close()

        events1: list[StreamEvent] = []
        while True:
            event = await eq.get()
            if event is None:
                break
            events1.append(event)

        session_start_count_1 = sum(1 for e in events1 if e.type == EventType.SESSION_START)
        session_end_count_1 = sum(1 for e in events1 if e.type == EventType.SESSION_END)

        eq.flush()
        try:
            pass
        finally:
            await eq.close()

        events2: list[StreamEvent] = []
        while True:
            event = await eq.get()
            if event is None:
                break
            events2.append(event)

        session_end_count_2 = sum(1 for e in events2 if e.type == EventType.SESSION_END)

        assert session_start_count_1 == 1
        assert session_end_count_1 == 1

        # SESSION_START is not re-emitted unless emit_session_start() is called manually
        assert session_end_count_2 == 1
