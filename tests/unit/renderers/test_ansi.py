"""Tests for the AnsiRenderer — zero-dependency ANSI escape-code renderer."""

from __future__ import annotations

import io

from strands_compose.renderers import AnsiRenderer
from strands_compose.types import EventType
from strands_compose.wire import StreamEvent

AGENT = "test-agent"


def _event(type_: str, **data: object) -> StreamEvent:
    """Build a StreamEvent with the given type and payload."""
    return StreamEvent(type=type_, agent_name=AGENT, data=dict(data))


class TestAnsiRenderer:
    """AnsiRenderer renders all event types to a text stream."""

    def _renderer(self) -> tuple[AnsiRenderer, io.StringIO]:
        buf = io.StringIO()
        return AnsiRenderer(file=buf), buf

    # -- Token streaming ---------------------------------------------------

    def test_token_written_inline(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.TOKEN, text="hello"))
        output = buf.getvalue()
        # Separator line is printed first, then the token text
        assert "RESPONDING" in output
        assert output.endswith("hello")

    def test_consecutive_tokens_concatenate(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.TOKEN, text="he"))
        r.render(_event(EventType.TOKEN, text="llo"))
        assert buf.getvalue().endswith("hello")

    def test_flush_terminates_token_stream(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.TOKEN, text="hello"))
        r.flush()
        assert buf.getvalue().endswith("\n")

    def test_flush_is_noop_when_not_in_tokens(self) -> None:
        r, buf = self._renderer()
        r.flush()
        assert buf.getvalue() == ""

    # -- Structured events break the token line ----------------------------

    def test_agent_start_breaks_token_stream(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.TOKEN, text="tok"))
        r.render(_event(EventType.AGENT_START))
        # Should contain a newline between "tok" and the agent_start line.
        output = buf.getvalue()
        assert "tok\n" in output
        assert AGENT in output

    # -- All event types produce output (or are intentionally silent) ------

    def test_agent_start(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.AGENT_START))
        assert AGENT in buf.getvalue()
        assert "starting" in buf.getvalue()

    def test_tool_start(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.TOOL_START, tool_name="search", tool_input={"q": "x"}))
        output = buf.getvalue()
        assert "search" in output
        assert "⚙" in output

    def test_tool_end_success(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.TOOL_END, status="success"))
        assert "✓" in buf.getvalue()

    def test_tool_end_error(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.TOOL_END, status="error", error="timeout"))
        output = buf.getvalue()
        assert "✗" in output
        assert "timeout" in output

    def test_complete(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.COMPLETE, usage={"input_tokens": 42, "output_tokens": 80}))
        output = buf.getvalue()
        assert "complete" in output
        assert "42" in output
        assert "80" in output

    def test_error(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.ERROR, message="something broke"))
        output = buf.getvalue()
        assert "ERROR" in output
        assert "something broke" in output

    def test_node_start(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.NODE_START, node_id="n1"))
        assert "n1" in buf.getvalue()

    def test_node_stop(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.NODE_STOP, node_id="n1"))
        assert "n1" in buf.getvalue()

    def test_handoff(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.HANDOFF, to_node_ids=["n2", "n3"]))
        output = buf.getvalue()
        assert "n2" in output
        assert "n3" in output

    def test_multiagent_start(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.MULTIAGENT_START, multiagent_type="graph"))
        assert "graph" in buf.getvalue()

    def test_multiagent_complete(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.MULTIAGENT_COMPLETE, multiagent_type="graph"))
        assert "graph" in buf.getvalue()

    def test_reasoning_is_displayed(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.REASONING, text="thinking…"))
        output = buf.getvalue()
        assert "REASONING" in output
        assert "thinking…" in output

    def test_reasoning_then_token_shows_both_separators(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.REASONING, text="hmm"))
        r.render(_event(EventType.TOKEN, text="answer"))
        output = buf.getvalue()
        assert "REASONING" in output
        assert "RESPONDING" in output
        assert "hmm" in output
        assert "answer" in output

    def test_separator_not_repeated_for_same_mode(self) -> None:
        r, buf = self._renderer()
        r.render(_event(EventType.TOKEN, text="a"))
        r.render(_event(EventType.TOKEN, text="b"))
        output = buf.getvalue()
        assert output.count("RESPONDING") == 1

    def test_unknown_event_is_silent(self) -> None:
        r, buf = self._renderer()
        r.render(_event("custom_event", info="x"))
        assert buf.getvalue() == ""

    # -- State transitions -------------------------------------------------

    def test_structured_event_after_tokens_inserts_newline(self) -> None:
        """Any non-token event must break the inline token stream."""
        r, buf = self._renderer()
        r.render(_event(EventType.TOKEN, text="partial"))
        r.render(_event(EventType.COMPLETE, usage={}))
        output = buf.getvalue()
        # "partial" followed by "\n" followed by the complete line
        idx_partial = output.index("partial")
        idx_newline = output.index("\n", idx_partial)
        assert idx_newline == idx_partial + len("partial")
