"""AnsiRenderer — StreamEvent -> terminal text (pure transform into a buffer).

Renders into a StringIO and asserts the renderer surfaces the event's key data
(agent name, node id, status). Formatting/colour is not pinned.

Agents delegated in the same turn run concurrently and interleave their events,
so the last tests cover serialising them back into one block per agent.
"""

from __future__ import annotations

import io

import pytest

from strands_compose.renderers import AnsiRenderer
from strands_compose.types import EntryDescriptor, EventType, SessionManifest, StreamEvent


def _render(*events: StreamEvent) -> str:
    buf = io.StringIO()
    renderer = AnsiRenderer(file=buf, separator_width=40)
    for event in events:
        renderer.render(event)
    renderer.flush()
    return buf.getvalue()


def _ev(kind, agent="worker", **data) -> StreamEvent:
    return StreamEvent(type=kind, agent_name=agent, data=data)


def _headers(out: str, agent: str, label: str) -> int:
    """Count the separator headers rendered for *agent* / *label*."""
    return out.count(f" {agent} \u2014 {label} ")


def test_token_text_is_written():
    assert "hello" in _render(_ev(EventType.TOKEN, text="hello"))


def test_reasoning_text_is_written():
    assert "thinking" in _render(_ev(EventType.REASONING, text="thinking"))


def test_leading_whitespace_token_does_not_open_responding_section():
    assert _render(_ev(EventType.TOKEN, text="\n")) == ""


def test_leading_whitespace_reasoning_does_not_open_reasoning_section():
    assert _render(_ev(EventType.REASONING, text=" \t")) == ""


def test_agent_start_shows_agent_name():
    assert "worker" in _render(_ev(EventType.AGENT_START))


def test_tool_start_shows_tool_name():
    out = _render(_ev(EventType.TOOL_START, tool_name="search", tool_input={"q": "x"}))
    assert "search" in out


def test_tool_end_error_shows_error_marker():
    out = _render(_ev(EventType.TOOL_END, status="error", error="boom"))
    assert "boom" in out


def test_agent_complete_shows_token_usage():
    out = _render(_ev(EventType.AGENT_COMPLETE, usage={"input_tokens": 3, "output_tokens": 2}))
    assert "3" in out and "2" in out


def test_node_events_show_node_id():
    out = _render(_ev(EventType.NODE_START, node_id="n1"), _ev(EventType.NODE_STOP, node_id="n1"))
    assert "n1" in out


def test_handoff_shows_target_nodes():
    assert "analyst" in _render(_ev(EventType.HANDOFF, to_node_ids=["analyst"]))


def test_multiagent_start_and_complete_render_kind():
    out = _render(
        _ev(EventType.MULTIAGENT_START, multiagent_type="swarm"),
        _ev(EventType.MULTIAGENT_COMPLETE, multiagent_type="swarm"),
    )
    assert "swarm" in out


def test_session_start_lists_entry_and_agents():
    manifest = SessionManifest(entry=EntryDescriptor(name="root", kind="agent")).model_dump()
    out = _render(
        StreamEvent(type=EventType.SESSION_START, agent_name="root", data={"manifest": manifest})
    )
    assert "root" in out


def test_session_end_shows_session_id():
    out = _render(
        StreamEvent(type=EventType.SESSION_END, agent_name="root", data={"session_id": "abc"})
    )
    assert "abc" in out


def test_mode_switch_between_reasoning_and_responding_renders_both():
    out = _render(_ev(EventType.REASONING, text="think"), _ev(EventType.TOKEN, text="answer"))
    assert "think" in out and "answer" in out


def test_interrupt_shows_name_reason_and_id():
    out = _render(
        _ev(
            EventType.INTERRUPT,
            interrupt_id="int-1",
            name="approve_refund",
            reason="needs a human",
        )
    )
    assert "approve_refund" in out
    assert "needs a human" in out
    assert "int-1" in out


# Minimal payload per event type — a new EventType with no entry fails the test
# below, which is the point: every type must reach a handler.
_MINIMAL_DATA: dict[str, dict] = {
    EventType.SESSION_START: {
        "manifest": SessionManifest(entry=EntryDescriptor(name="root", kind="agent")).model_dump()
    },
    EventType.SESSION_END: {"session_id": "s1"},
    EventType.TOKEN: {"text": "hi"},
    EventType.REASONING: {"text": "think"},
    EventType.AGENT_START: {},
    EventType.TOOL_START: {"tool_name": "search", "tool_input": {}},
    EventType.TOOL_END: {"status": "success"},
    EventType.AGENT_COMPLETE: {"usage": {}},
    EventType.INTERRUPT: {"interrupt_id": "i1", "name": "ask", "reason": "why"},
    EventType.ERROR: {"text": "boom"},
    EventType.NODE_START: {"node_id": "n1"},
    EventType.NODE_STOP: {"node_id": "n1"},
    EventType.HANDOFF: {"to_node_ids": ["analyst"]},
    EventType.MULTIAGENT_START: {"multiagent_type": "swarm"},
    EventType.MULTIAGENT_COMPLETE: {"multiagent_type": "swarm"},
}


@pytest.mark.parametrize("kind", list(EventType))
def test_every_event_type_renders_something(kind):
    """No event type may be silently dropped by the renderer."""
    out = _render(StreamEvent(type=kind, agent_name="worker", data=_MINIMAL_DATA[kind]))
    assert out != ""


def test_concurrent_agents_get_one_header_and_a_contiguous_block():
    out = _render(
        _ev(EventType.TOKEN, agent="researcher", text="aaa"),
        _ev(EventType.TOKEN, agent="writer", text="xxx"),
        _ev(EventType.TOKEN, agent="researcher", text="bbb"),
        _ev(EventType.TOKEN, agent="writer", text="yyy"),
        _ev(EventType.AGENT_COMPLETE, agent="researcher", usage={}),
        _ev(EventType.AGENT_COMPLETE, agent="writer", usage={}),
    )
    assert "aaabbb" in out and "xxxyyy" in out
    assert _headers(out, "researcher", "RESPONDING") == 1
    assert _headers(out, "writer", "RESPONDING") == 1


def test_streaming_sub_agent_takes_over_when_the_live_one_finishes():
    out = _render(
        _ev(EventType.TOOL_START, agent="main", tool_name="researcher", tool_input={}),
        _ev(EventType.TOOL_START, agent="main", tool_name="writer", tool_input={}),
        _ev(EventType.TOKEN, agent="researcher", text="facts"),
        _ev(EventType.TOKEN, agent="writer", text="draft"),
        _ev(EventType.AGENT_COMPLETE, agent="researcher", usage={}),
        _ev(EventType.TOOL_END, agent="main", status="success"),
        _ev(EventType.TOKEN, agent="writer", text=" continued"),
        _ev(EventType.AGENT_COMPLETE, agent="writer", usage={}),
        _ev(EventType.TOOL_END, agent="main", status="success"),
        _ev(EventType.TOKEN, agent="main", text="synthesis"),
        _ev(EventType.AGENT_COMPLETE, agent="main", usage={}),
    )
    assert "draft continued" in out
    assert out.index("facts") < out.index("draft") < out.index("synthesis")


def test_delegator_waiting_on_tools_does_not_take_the_terminal():
    out = _render(
        _ev(EventType.TOOL_START, agent="main", tool_name="researcher", tool_input={}),
        _ev(EventType.TOOL_START, agent="main", tool_name="writer", tool_input={}),
        _ev(EventType.TOKEN, agent="researcher", text="facts"),
        _ev(EventType.AGENT_COMPLETE, agent="researcher", usage={}),
        _ev(EventType.TOOL_END, agent="main", status="success"),
        _ev(EventType.TOKEN, agent="writer", text="draft"),
        _ev(EventType.AGENT_COMPLETE, agent="writer", usage={}),
        _ev(EventType.TOOL_END, agent="main", status="success"),
        _ev(EventType.TOKEN, agent="main", text="synthesis"),
        _ev(EventType.AGENT_COMPLETE, agent="main", usage={}),
    )
    assert out.index("facts") < out.index("draft") < out.index("synthesis")


def test_buffered_output_survives_a_missing_terminal_event():
    out = _render(
        _ev(EventType.TOKEN, agent="researcher", text="aaa"),
        _ev(EventType.TOKEN, agent="writer", text="xxx"),
    )
    assert "xxx" in out


def test_flush_resets_state_between_turns():
    buf = io.StringIO()
    renderer = AnsiRenderer(file=buf, separator_width=40)
    for _ in range(2):
        renderer.render(_ev(EventType.TOKEN, agent="main", text="hi"))
        renderer.flush()
    assert _headers(buf.getvalue(), "main", "RESPONDING") == 2
