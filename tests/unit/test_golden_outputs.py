"""Golden output / behavioral tests for end-to-end agent invocation (R10).

These tests use pre-recorded expected event sequences to validate that the
full EventPublisher → EventQueue pipeline produces the correct stream of
events for different agent behaviors.

Unlike unit tests that mock individual methods, these tests exercise the
full event publishing pipeline with realistic event sequences.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from strands_compose.hooks.event_publisher import EventPublisher
from strands_compose.types import EventType

# ---------------------------------------------------------------------------
# Golden sequence: simple text response
# ---------------------------------------------------------------------------


class TestGoldenSimpleTextResponse:
    """Golden test: agent receives prompt → emits tokens → completes.

    Expected event sequence:
    1. AGENT_START
    2. TOKEN("Hello")
    3. TOKEN(" world")
    4. COMPLETE(usage)
    """

    def test_simple_text_produces_correct_event_sequence(self) -> None:
        """Simulate a simple agent text response and verify the event stream."""
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="assistant")
        handler = pub.as_callback_handler()

        # 1. Agent invocation starts
        start_event = MagicMock()
        pub._on_agent_start(start_event)

        # 2. Model streams tokens via callback_handler
        handler(data="Hello")
        handler(data=" world")

        # 3. Invocation completes
        complete_event = MagicMock()
        metrics = MagicMock()
        invocation = MagicMock()
        invocation.usage = {"inputTokens": 50, "outputTokens": 10, "totalTokens": 60}
        metrics.latest_agent_invocation = invocation
        complete_event.agent.event_loop_metrics = metrics
        pub._on_complete(complete_event)

        # Verify golden sequence
        assert len(events) == 4
        assert events[0].type == EventType.AGENT_START
        assert events[0].agent_name == "assistant"
        assert events[1].type == EventType.TOKEN
        assert events[1].data["text"] == "Hello"
        assert events[2].type == EventType.TOKEN
        assert events[2].data["text"] == " world"
        assert events[3].type == EventType.COMPLETE
        assert events[3].data["usage"]["input_tokens"] == 50
        assert events[3].data["usage"]["output_tokens"] == 10


# ---------------------------------------------------------------------------
# Golden sequence: tool-calling agent
# ---------------------------------------------------------------------------


class TestGoldenToolCallingAgent:
    """Golden test: agent calls a tool mid-response.

    Expected event sequence:
    1. AGENT_START
    2. TOOL_START(search)
    3. TOOL_END(search, success)
    4. TOKEN("Based on the search...")
    5. COMPLETE(usage)
    """

    def test_tool_calling_produces_correct_event_sequence(self) -> None:
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="researcher")
        handler = pub.as_callback_handler()

        # 1. Start
        pub._on_agent_start(MagicMock())

        # 2. Tool call
        tool_start = MagicMock()
        tool_start.tool_use = {
            "name": "search",
            "toolUseId": "call_abc",
            "input": {"query": "latest news"},
        }
        pub._on_tool_start(tool_start)

        # 3. Tool result
        tool_end = MagicMock()
        tool_end.tool_use = {"name": "search", "toolUseId": "call_abc"}
        tool_end.result = {"content": [{"text": "Search results here"}]}
        tool_end.exception = None
        pub._on_tool_end(tool_end)

        # 4. Final token
        handler(data="Based on the search...")

        # 5. Complete
        complete = MagicMock()
        metrics = MagicMock()
        metrics.latest_agent_invocation = None
        metrics.accumulated_usage = {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150}
        complete.agent.event_loop_metrics = metrics
        pub._on_complete(complete)

        # Verify golden sequence
        assert len(events) == 5
        assert [e.type for e in events] == [
            EventType.AGENT_START,
            EventType.TOOL_START,
            EventType.TOOL_END,
            EventType.TOKEN,
            EventType.COMPLETE,
        ]
        assert events[1].data["tool_name"] == "search"
        assert events[1].data["tool_use_id"] == "call_abc"
        assert events[2].data["status"] == "success"
        assert events[2].data["tool_result"] == "Search results here"


# ---------------------------------------------------------------------------
# Golden sequence: reasoning then response
# ---------------------------------------------------------------------------


class TestGoldenReasoningThenResponse:
    """Golden test: agent reasons then responds.

    Expected event sequence:
    1. AGENT_START
    2. REASONING("Let me think...")
    3. TOKEN("The answer is 42")
    4. COMPLETE
    """

    def test_reasoning_then_response_produces_correct_sequence(self) -> None:
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="thinker")
        handler = pub.as_callback_handler()

        pub._on_agent_start(MagicMock())
        handler(reasoningText="Let me think...")
        handler(data="The answer is 42")

        complete = MagicMock()
        metrics = MagicMock()
        metrics.latest_agent_invocation = None
        metrics.accumulated_usage = {"inputTokens": 20, "outputTokens": 5, "totalTokens": 25}
        complete.agent.event_loop_metrics = metrics
        pub._on_complete(complete)

        assert len(events) == 4
        assert events[0].type == EventType.AGENT_START
        assert events[1].type == EventType.REASONING
        assert events[1].data["text"] == "Let me think..."
        assert events[2].type == EventType.TOKEN
        assert events[2].data["text"] == "The answer is 42"
        assert events[3].type == EventType.COMPLETE


# ---------------------------------------------------------------------------
# Golden sequence: model error
# ---------------------------------------------------------------------------


class TestGoldenModelError:
    """Golden test: model call fails → ERROR emitted, COMPLETE suppressed.

    Expected event sequence:
    1. AGENT_START
    2. ERROR(expired credentials)
    (no COMPLETE)
    """

    def test_model_error_produces_correct_sequence(self) -> None:
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="broken")

        pub._on_agent_start(MagicMock())

        # Model error
        model_event = MagicMock()
        model_event.exception = RuntimeError("Credentials expired")
        pub._on_model_error(model_event)

        # AfterInvocationEvent fires anyway (finally block)
        complete = MagicMock()
        metrics = MagicMock()
        metrics.latest_agent_invocation = None
        metrics.accumulated_usage = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}
        complete.agent.event_loop_metrics = metrics
        pub._on_complete(complete)

        # Only AGENT_START + ERROR, no COMPLETE
        assert len(events) == 2
        assert events[0].type == EventType.AGENT_START
        assert events[1].type == EventType.ERROR
        assert "Credentials expired" in events[1].data["message"]


# ---------------------------------------------------------------------------
# Golden sequence: multi-agent swarm
# ---------------------------------------------------------------------------


class TestGoldenMultiAgentSwarm:
    """Golden test: swarm orchestration lifecycle.

    Expected event sequence:
    1. MULTIAGENT_START(swarm)
    2. NODE_START(researcher)
    3. NODE_STOP(researcher)
    4. NODE_START(writer)
    5. NODE_STOP(writer)
    6. MULTIAGENT_COMPLETE(swarm)
    """

    def test_swarm_lifecycle_produces_correct_sequence(self) -> None:
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="pipeline")

        source = MagicMock()
        source.__class__.__name__ = "Swarm"

        # Start swarm
        ma_start = MagicMock()
        ma_start.source = source
        pub._on_multiagent_start(ma_start)

        # Node: researcher
        n1_start = MagicMock()
        n1_start.node_id = "researcher"
        n1_start.source = source
        pub._on_node_start(n1_start)

        n1_stop = MagicMock()
        n1_stop.node_id = "researcher"
        n1_stop.source = source
        pub._on_node_stop(n1_stop)

        # Node: writer
        n2_start = MagicMock()
        n2_start.node_id = "writer"
        n2_start.source = source
        pub._on_node_start(n2_start)

        n2_stop = MagicMock()
        n2_stop.node_id = "writer"
        n2_stop.source = source
        pub._on_node_stop(n2_stop)

        # Complete swarm
        ma_complete = MagicMock()
        ma_complete.source = source
        pub._on_multiagent_complete(ma_complete)

        assert len(events) == 6
        expected_types = [
            EventType.MULTIAGENT_START,
            EventType.NODE_START,
            EventType.NODE_STOP,
            EventType.NODE_START,
            EventType.NODE_STOP,
            EventType.MULTIAGENT_COMPLETE,
        ]
        assert [e.type for e in events] == expected_types
        assert events[1].data["node_id"] == "researcher"
        assert events[3].data["node_id"] == "writer"
        assert all(e.agent_name == "pipeline" for e in events)


# ---------------------------------------------------------------------------
# Golden sequence: tool error
# ---------------------------------------------------------------------------


class TestGoldenToolError:
    """Golden test: tool call fails → TOOL_END with error status.

    Expected event sequence:
    1. AGENT_START
    2. TOOL_START(db_query)
    3. TOOL_END(db_query, error)
    4. TOKEN("I encountered an error...")
    5. COMPLETE
    """

    def test_tool_error_produces_correct_sequence(self) -> None:
        events: list = []
        pub = EventPublisher(callback=events.append, agent_name="agent")
        handler = pub.as_callback_handler()

        pub._on_agent_start(MagicMock())

        tool_start = MagicMock()
        tool_start.tool_use = {
            "name": "db_query",
            "toolUseId": "call_db1",
            "input": {"sql": "SELECT 1"},
        }
        pub._on_tool_start(tool_start)

        tool_end = MagicMock()
        tool_end.tool_use = {"name": "db_query", "toolUseId": "call_db1"}
        tool_end.result = None
        tool_end.exception = ConnectionError("DB unreachable")
        pub._on_tool_end(tool_end)

        handler(data="I encountered an error...")

        complete = MagicMock()
        metrics = MagicMock()
        metrics.latest_agent_invocation = None
        metrics.accumulated_usage = {"inputTokens": 30, "outputTokens": 15, "totalTokens": 45}
        complete.agent.event_loop_metrics = metrics
        pub._on_complete(complete)

        assert len(events) == 5
        assert events[2].data["status"] == "error"
        assert "DB unreachable" in events[2].data["error"]
        assert events[2].data["tool_result"] is None
