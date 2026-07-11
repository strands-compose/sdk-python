"""AnsiRenderer — StreamEvent -> terminal text (pure transform into a buffer).

Renders into a StringIO and asserts the renderer surfaces the event's key data
(agent name, node id, status). Formatting/colour is not pinned.
"""

from __future__ import annotations

import io

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


def test_token_text_is_written():
    assert "hello" in _render(_ev(EventType.TOKEN, text="hello"))


def test_reasoning_text_is_written():
    assert "thinking" in _render(_ev(EventType.REASONING, text="thinking"))


def test_leading_whitespace_token_does_not_open_responding_section():
    assert _render(_ev(EventType.TOKEN, text="\n")) == ""


def test_leading_whitespace_reasoning_does_not_open_reasoning_section():
    assert _render(_ev(EventType.REASONING, text=" \t")) == ""


def test_whitespace_after_content_is_written():
    assert "hello\n" in _render(
        _ev(EventType.TOKEN, text="hello"),
        _ev(EventType.TOKEN, text="\n"),
    )
    assert "thinking\n" in _render(
        _ev(EventType.REASONING, text="thinking"),
        _ev(EventType.REASONING, text="\n"),
    )


def test_agent_start_shows_agent_name():
    assert "worker" in _render(_ev(EventType.AGENT_START))


def test_tool_start_shows_tool_label():
    out = _render(_ev(EventType.TOOL_START, tool_name="search", tool_input={"q": "x"}))
    assert "search" in out


def test_tool_end_error_shows_error_marker():
    out = _render(_ev(EventType.TOOL_END, status="error", error="boom"))
    assert "boom" in out


def test_tool_end_success_renders():
    assert _render(_ev(EventType.TOOL_END, status="success")) != ""


def test_agent_complete_shows_token_usage():
    out = _render(_ev(EventType.AGENT_COMPLETE, usage={"input_tokens": 3, "output_tokens": 2}))
    assert "3" in out and "2" in out


def test_error_event_is_rendered():
    assert "ERROR" in _render(_ev(EventType.ERROR, message="bad"))


def test_node_events_show_node_id():
    out = _render(_ev(EventType.NODE_START, node_id="n1"), _ev(EventType.NODE_STOP, node_id="n1"))
    assert out.count("n1") == 2


def test_handoff_shows_target_nodes():
    assert "analyst" in _render(_ev(EventType.HANDOFF, to_node_ids=["analyst"]))


def test_multiagent_start_and_complete_render_kind():
    out = _render(
        _ev(EventType.MULTIAGENT_START, multiagent_type="swarm"),
        _ev(EventType.MULTIAGENT_COMPLETE, multiagent_type="swarm"),
    )
    assert out.count("swarm") == 2


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
