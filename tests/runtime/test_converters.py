"""StreamEvent -> protocol chunk converters (OpenAI + raw pass-through).

The OpenAI chunk shape is a real external contract, so structural assertions
here are legitimate — but we assert on shape/fields, not exact prose.
"""

from __future__ import annotations

from strands_compose.converters.openai import OpenAIStreamConverter
from strands_compose.converters.raw import RawStreamConverter
from strands_compose.types import EventType, StreamEvent


def _openai() -> OpenAIStreamConverter:
    return OpenAIStreamConverter(entry_agent_name="entry")


def test_entry_token_becomes_openai_content_delta():
    chunks = _openai().convert(
        StreamEvent(type=EventType.TOKEN, agent_name="entry", data={"text": "hi"})
    )
    assert chunks[0]["object"] == "chat.completion.chunk"
    assert chunks[0]["choices"][0]["delta"]["content"] == "hi"


def test_sub_agent_token_is_suppressed_in_compact_mode():
    chunks = _openai().convert(
        StreamEvent(type=EventType.TOKEN, agent_name="worker", data={"text": "x"})
    )
    assert chunks == []


def test_agent_complete_emits_stop_with_usage():
    event = StreamEvent(
        type=EventType.AGENT_COMPLETE,
        agent_name="entry",
        data={"usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}},
    )
    chunks = _openai().convert(event)
    finish = chunks[-1]
    assert finish["choices"][0]["finish_reason"] == "stop"
    assert finish["usage"]["total_tokens"] == 15


def test_error_event_emits_error_finish_reason():
    chunks = _openai().convert(
        StreamEvent(type=EventType.ERROR, agent_name="entry", data={"message": "boom"})
    )
    assert chunks[0]["choices"][0]["finish_reason"] == "error"


def test_openai_done_marker_is_openai_sentinel():
    assert _openai().done_marker() == "data: [DONE]\n\n"


def test_raw_converter_passes_event_through_as_dict():
    event = StreamEvent(type=EventType.TOKEN, agent_name="a", data={"text": "hi"})
    chunks = RawStreamConverter().convert(event)
    assert chunks == [event.asdict()]


def test_raw_converter_has_no_done_marker():
    assert RawStreamConverter().done_marker() == ""


def test_reasoning_populates_both_reasoning_fields_in_both_mode():
    event = StreamEvent(type=EventType.REASONING, agent_name="entry", data={"text": "thinking"})
    delta = _openai().convert(event)[0]["choices"][0]["delta"]
    assert delta["reasoning_content"] == "thinking"
    assert delta["reasoning"] == "thinking"


def test_tool_start_then_end_renders_a_details_block():
    conv = _openai()
    conv.convert(
        StreamEvent(
            type=EventType.TOOL_START,
            agent_name="entry",
            data={"tool_use_id": "t1", "tool_name": "search", "tool_input": {"q": "x"}},
        )
    )
    chunks = conv.convert(
        StreamEvent(
            type=EventType.TOOL_END,
            agent_name="entry",
            data={"tool_use_id": "t1", "tool_result": "found it"},
        )
    )
    content = chunks[0]["choices"][0]["delta"]["content"]
    assert "search" in content
    assert "found it" in content


def test_node_start_then_stop_renders_a_details_block():
    conv = _openai()
    conv.convert(
        StreamEvent(type=EventType.NODE_START, agent_name="entry", data={"node_id": "researcher"})
    )
    chunks = conv.convert(
        StreamEvent(type=EventType.NODE_STOP, agent_name="entry", data={"node_id": "researcher"})
    )
    assert "researcher" in chunks[0]["choices"][0]["delta"]["content"]


def test_multiagent_complete_emits_terminal_stop():
    event = StreamEvent(type=EventType.MULTIAGENT_COMPLETE, agent_name="entry", data={"usage": {}})
    chunks = _openai().convert(event)
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_usage_chunk_mode_emits_separate_trailing_usage_chunk():
    conv = OpenAIStreamConverter(entry_agent_name="entry", emit_usage_chunk=True)
    event = StreamEvent(
        type=EventType.AGENT_COMPLETE,
        agent_name="entry",
        data={"usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}},
    )
    chunks = conv.convert(event)
    assert chunks[-1]["choices"] == []
    assert chunks[-1]["usage"]["total_tokens"] == 2


def test_reset_clears_stream_state():
    conv = _openai()
    conv.convert(StreamEvent(type=EventType.TOKEN, agent_name="entry", data={"text": "hi"}))
    conv.reset()
    # After reset the role prelude is sent again on the next content chunk.
    delta = conv.convert(
        StreamEvent(type=EventType.TOKEN, agent_name="entry", data={"text": "again"})
    )[0]["choices"][0]["delta"]
    assert delta.get("role") == "assistant"
