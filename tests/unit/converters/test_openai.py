"""Scenario tests for OpenAIStreamConverter.

Each test feeds a realistic sequence of stream events and validates the
resulting OpenAI ``chat.completion.chunk`` output end-to-end.
"""

from __future__ import annotations

import pytest

from strands_compose.converters.openai import OpenAIStreamConverter
from strands_compose.types import EventType
from strands_compose.wire import StreamEvent

AGENT = "assistant"
SUB = "researcher"  # a different sub-agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ev(type_: str, agent: str = AGENT, **data: object) -> StreamEvent:
    """Build a StreamEvent with the given type, agent_name, and payload."""
    return StreamEvent(type=type_, agent_name=agent, data=dict(data))


def _flush(conv: OpenAIStreamConverter, events: list[StreamEvent]) -> list[dict]:
    """Feed all events through the converter and return all resulting chunks."""
    out: list[dict] = []
    for ev in events:
        out.extend(conv.convert(ev))
    return out


def _delta(chunk: dict) -> dict:
    """Return the delta dict from the first choice of a chunk."""
    return chunk["choices"][0]["delta"]


def _finish(chunk: dict) -> str | None:
    """Return the finish_reason from the first choice of a chunk."""
    return chunk["choices"][0]["finish_reason"]


@pytest.fixture
def converter() -> OpenAIStreamConverter:
    """Create a default OpenAIStreamConverter for one test."""
    return OpenAIStreamConverter(
        entry_agent_name=AGENT,
        model_label="agent-model",
        completion_id="chk-id-djrue5rjregerg234234",
        reasoning_field_mode="both",
        tool_result_render="details_block",
        emit_usage_chunk=False,
        verbosity="compact",
    )


@pytest.fixture
def deepseek_converter() -> OpenAIStreamConverter:
    """Create a converter that emits only DeepSeek reasoning fields."""
    return OpenAIStreamConverter(entry_agent_name=AGENT, reasoning_field_mode="deepseek")


@pytest.fixture
def openrouter_converter() -> OpenAIStreamConverter:
    """Create a converter that emits only OpenRouter reasoning fields."""
    return OpenAIStreamConverter(entry_agent_name=AGENT, reasoning_field_mode="openrouter")


@pytest.fixture
def no_reasoning_converter() -> OpenAIStreamConverter:
    """Create a converter that suppresses reasoning fields."""
    return OpenAIStreamConverter(entry_agent_name=AGENT, reasoning_field_mode="none")


@pytest.fixture
def no_details_converter() -> OpenAIStreamConverter:
    """Create a converter that suppresses details-block HTML."""
    return OpenAIStreamConverter(entry_agent_name=AGENT, tool_result_render="none")


@pytest.fixture
def gpt4o_converter() -> OpenAIStreamConverter:
    """Create a converter with a custom OpenAI model label."""
    return OpenAIStreamConverter(entry_agent_name=AGENT, model_label="gpt-4o")


@pytest.fixture
def entry_name_converter() -> OpenAIStreamConverter:
    """Create a converter whose model defaults to entry_agent_name."""
    return OpenAIStreamConverter(entry_agent_name=AGENT)


# ---------------------------------------------------------------------------
# Plain text stream
# ---------------------------------------------------------------------------


class TestPlainTextStream:
    """Simple text-only response: tokens then COMPLETE."""

    def test_token_events_produce_content_delta_chunks(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """Each TOKEN event becomes one chunk with delta.content."""
        conv = converter
        chunks = _flush(
            conv,
            [
                _ev(EventType.TOKEN, text="Hello"),
                _ev(EventType.TOKEN, text=" world"),
            ],
        )

        assert len(chunks) == 2
        assert _delta(chunks[0])["content"] == "Hello"
        assert _delta(chunks[1])["content"] == " world"

    def test_role_assistant_sent_on_first_chunk_only(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """role='assistant' appears only in the first delta."""
        conv = converter
        chunks = _flush(
            conv,
            [
                _ev(EventType.TOKEN, text="a"),
                _ev(EventType.TOKEN, text="b"),
            ],
        )

        assert _delta(chunks[0]).get("role") == "assistant"
        assert "role" not in _delta(chunks[1])

    def test_complete_emits_stop_finish_reason(self, converter: OpenAIStreamConverter) -> None:
        """COMPLETE produces a single chunk with finish_reason='stop' and empty delta."""
        conv = converter
        chunks = _flush(
            conv,
            [
                _ev(EventType.TOKEN, text="hi"),
                _ev(EventType.COMPLETE, usage={}),
            ],
        )

        terminal = chunks[-1]
        assert _finish(terminal) == "stop"
        assert _delta(terminal) == {}

    def test_completion_id_is_consistent_across_stream(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """All chunks in one stream share the same completion id."""
        conv = converter
        chunks = _flush(
            conv,
            [
                _ev(EventType.TOKEN, text="x"),
                _ev(EventType.TOKEN, text="y"),
                _ev(EventType.COMPLETE, usage={}),
            ],
        )

        ids = {c["id"] for c in chunks}
        assert len(ids) == 1
        assert next(iter(ids)) == "chk-id-djrue5rjregerg234234"

    def test_usage_fields_mapped_to_openai_names(self, converter: OpenAIStreamConverter) -> None:
        """input_tokens/output_tokens are mapped to prompt_tokens/completion_tokens."""
        conv = converter
        chunks = _flush(
            conv,
            [
                _ev(
                    EventType.COMPLETE,
                    usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                ),
            ],
        )

        usage = chunks[0]["usage"]
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 20
        assert usage["total_tokens"] == 30

    def test_all_chunks_carry_required_openai_envelope_fields(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """Every chunk has id, object, created, model and choices."""
        conv = converter
        chunks = _flush(
            conv,
            [
                _ev(EventType.TOKEN, text="hi"),
                _ev(EventType.COMPLETE, usage={}),
            ],
        )

        for chunk in chunks:
            assert "id" in chunk
            assert chunk["object"] == "chat.completion.chunk"
            assert isinstance(chunk["created"], int)
            assert isinstance(chunk["model"], str)
            assert isinstance(chunk["choices"], list)


# ---------------------------------------------------------------------------
# Reasoning stream
# ---------------------------------------------------------------------------


class TestReasoningStream:
    """Reasoning tokens emitted before the main response."""

    def test_reasoning_emits_both_fields_by_default(self, converter: OpenAIStreamConverter) -> None:
        """Default mode='both' puts text in reasoning_content AND reasoning."""
        conv = converter
        chunks = _flush(conv, [_ev(EventType.REASONING, text="thinking")])

        delta = _delta(chunks[0])
        assert delta["reasoning_content"] == "thinking"
        assert delta["reasoning"] == "thinking"

    def test_reasoning_mode_deepseek_omits_reasoning_field(
        self, deepseek_converter: OpenAIStreamConverter
    ) -> None:
        """mode='deepseek' includes only reasoning_content."""
        conv = deepseek_converter
        chunks = _flush(conv, [_ev(EventType.REASONING, text="step")])

        delta = _delta(chunks[0])
        assert "reasoning_content" in delta
        assert "reasoning" not in delta

    def test_reasoning_mode_openrouter_omits_reasoning_content(
        self, openrouter_converter: OpenAIStreamConverter
    ) -> None:
        """mode='openrouter' includes only reasoning."""
        conv = openrouter_converter
        chunks = _flush(conv, [_ev(EventType.REASONING, text="step")])

        delta = _delta(chunks[0])
        assert "reasoning" in delta
        assert "reasoning_content" not in delta

    def test_reasoning_mode_none_drops_chunks(
        self, no_reasoning_converter: OpenAIStreamConverter
    ) -> None:
        """mode='none' produces no chunks for REASONING events."""
        conv = no_reasoning_converter
        chunks = _flush(conv, [_ev(EventType.REASONING, text="hidden")])

        assert chunks == []

    def test_role_sent_with_first_reasoning_chunk_not_repeated(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """role='assistant' appears on first REASONING chunk; omitted on subsequent."""
        conv = converter
        c1 = conv.convert(_ev(EventType.REASONING, text="a"))
        c2 = conv.convert(_ev(EventType.REASONING, text="b"))

        assert _delta(c1[0]).get("role") == "assistant"
        assert "role" not in _delta(c2[0])

    def test_token_after_reasoning_does_not_repeat_role(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """role is sent exactly once; TOKEN after REASONING has no role."""
        conv = converter
        conv.convert(_ev(EventType.REASONING, text="hmm"))
        chunks = conv.convert(_ev(EventType.TOKEN, text="answer"))

        assert "role" not in _delta(chunks[0])


# ---------------------------------------------------------------------------
# Tool call stream
# ---------------------------------------------------------------------------


class TestToolCallStream:
    """TOOL_START / TOOL_END lifecycle with details-block rendering."""

    def test_tool_start_emits_no_chunks(self, converter: OpenAIStreamConverter) -> None:
        """TOOL_START produces nothing; the completed call renders on TOOL_END."""
        conv = converter
        chunks = conv.convert(
            _ev(
                EventType.TOOL_START,
                tool_name="web_search",
                tool_use_id="call_1",
                tool_input={"q": "strands agents"},
            )
        )

        assert chunks == []

    def test_tool_end_emits_details_closer_with_result(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """TOOL_END emits a completed ``<details done="true">`` block."""
        conv = converter
        conv.convert(_ev(EventType.TOOL_START, tool_name="calc", tool_use_id="c1", tool_input={}))
        chunks = conv.convert(_ev(EventType.TOOL_END, tool_use_id="c1", tool_result="4"))

        assert len(chunks) == 1
        html = _delta(chunks[0])["content"]
        assert 'type="tool_calls"' in html
        assert 'done="true"' in html
        assert 'name="calc"' in html
        assert "4" in html

    def test_finish_reason_is_stop_never_tool_calls(self, converter: OpenAIStreamConverter) -> None:
        """COMPLETE after tool use emits stop, never tool_calls (would cause client loop)."""
        conv = converter
        _flush(
            conv,
            [
                _ev(EventType.TOOL_START, tool_name="t", tool_use_id="c", tool_input={}),
                _ev(EventType.TOOL_END, tool_use_id="c", result="ok"),
            ],
        )
        chunks = conv.convert(_ev(EventType.COMPLETE, usage={}))

        assert _finish(chunks[0]) == "stop"

    def test_no_native_tool_calls_delta_is_ever_emitted(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """No chunk in the stream carries ``delta.tool_calls`` — only HTML closers."""
        conv = converter
        chunks = _flush(
            conv,
            [
                _ev(EventType.TOOL_START, tool_name="a", tool_use_id="x1", tool_input={}),
                _ev(EventType.TOOL_END, tool_use_id="x1", tool_result="1"),
                _ev(EventType.TOOL_START, tool_name="b", tool_use_id="x2", tool_input={}),
                _ev(EventType.TOOL_END, tool_use_id="x2", tool_result="2"),
                _ev(EventType.COMPLETE, usage={}),
            ],
        )

        for chunk in chunks:
            assert "tool_calls" not in _delta(chunk)

    def test_tool_result_render_none_suppresses_all_tool_chunks(
        self, no_details_converter: OpenAIStreamConverter
    ) -> None:
        """``tool_result_render='none'`` suppresses both TOOL_START and TOOL_END output."""
        conv = no_details_converter
        start_chunks = conv.convert(
            _ev(EventType.TOOL_START, tool_name="fn", tool_use_id="c", tool_input={})
        )
        end_chunks = conv.convert(_ev(EventType.TOOL_END, tool_use_id="c", tool_result="ok"))

        assert start_chunks == []
        assert end_chunks == []


# ---------------------------------------------------------------------------
# Sub-agent suppression
# ---------------------------------------------------------------------------


class TestSubAgentSuppression:
    """Events from agents other than entry_agent_name are silently dropped."""

    def test_token_from_sub_agent_produces_no_chunks(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """TOKEN from a sub-agent is suppressed."""
        conv = converter
        chunks = conv.convert(_ev(EventType.TOKEN, agent=SUB, text="sub output"))

        assert chunks == []

    def test_complete_from_sub_agent_produces_no_chunks(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """COMPLETE from a sub-agent does not close the stream."""
        conv = converter
        chunks = conv.convert(_ev(EventType.COMPLETE, agent=SUB, usage={}))

        assert chunks == []

    def test_tool_start_from_sub_agent_is_suppressed(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """TOOL_START from a sub-agent is suppressed."""
        conv = converter
        chunks = conv.convert(
            _ev(
                EventType.TOOL_START,
                agent=SUB,
                tool_name="t",
                tool_use_id="c",
                tool_input={},
            )
        )

        assert chunks == []

    def test_reasoning_from_sub_agent_is_suppressed(self, converter: OpenAIStreamConverter) -> None:
        """REASONING from a sub-agent is suppressed."""
        conv = converter
        chunks = conv.convert(_ev(EventType.REASONING, agent=SUB, text="sub thinks"))

        assert chunks == []


# ---------------------------------------------------------------------------
# NODE_START / NODE_STOP (multi-agent orchestration)
# ---------------------------------------------------------------------------


class TestNodeStartStop:
    """NODE_START/NODE_STOP surfaces sub-agent invocations as completed details blocks."""

    def test_node_start_emits_no_chunks(self, converter: OpenAIStreamConverter) -> None:
        """NODE_START produces nothing; the node renders as a closer on NODE_STOP."""
        conv = converter
        chunks = conv.convert(_ev(EventType.NODE_START, node_id="researcher"))

        assert chunks == []

    def test_node_stop_emits_details_closer(self, converter: OpenAIStreamConverter) -> None:
        """NODE_STOP emits the completed ``<details done="true">`` block for the node."""
        conv = converter
        conv.convert(_ev(EventType.NODE_START, node_id="researcher"))
        chunks = conv.convert(_ev(EventType.NODE_STOP, node_id="researcher"))

        assert len(chunks) == 1
        html = _delta(chunks[0])["content"]
        assert 'done="true"' in html
        assert 'name="researcher"' in html

    def test_duplicate_node_start_is_ignored(self, converter: OpenAIStreamConverter) -> None:
        """A second NODE_START for the same node_id produces no output."""
        conv = converter
        conv.convert(_ev(EventType.NODE_START, node_id="researcher"))
        chunks = conv.convert(_ev(EventType.NODE_START, node_id="researcher"))

        assert chunks == []

    def test_node_start_from_sub_agent_is_suppressed(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """NODE_START from a sub-agent is suppressed."""
        conv = converter
        chunks = conv.convert(_ev(EventType.NODE_START, agent=SUB, node_id="worker"))

        assert chunks == []


# ---------------------------------------------------------------------------
# MULTIAGENT_COMPLETE
# ---------------------------------------------------------------------------


class TestMultiagentComplete:
    """MULTIAGENT_COMPLETE ends the stream for the entry agent."""

    def test_multiagent_complete_produces_stop_for_entry_agent(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """MULTIAGENT_COMPLETE from entry agent emits finish_reason='stop'."""
        conv = converter
        chunks = conv.convert(_ev(EventType.MULTIAGENT_COMPLETE, usage={}))

        assert len(chunks) == 1
        assert _finish(chunks[0]) == "stop"

    def test_multiagent_complete_from_sub_agent_is_suppressed(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """MULTIAGENT_COMPLETE from sub-agent produces no output."""
        conv = converter
        chunks = conv.convert(_ev(EventType.MULTIAGENT_COMPLETE, agent=SUB, usage={}))

        assert chunks == []


# ---------------------------------------------------------------------------
# Error scenario
# ---------------------------------------------------------------------------


class TestErrorScenario:
    """ERROR event terminates stream immediately."""

    def test_error_produces_error_finish_reason_and_error_field(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """ERROR chunk has finish_reason='error' and a top-level error field."""
        conv = converter
        chunks = conv.convert(_ev(EventType.ERROR, message="Rate limit hit"))

        assert len(chunks) == 1
        assert _finish(chunks[0]) == "error"
        assert chunks[0]["error"]["message"] == "Rate limit hit"
        assert chunks[0]["error"]["type"] == "agent_error"

    def test_error_default_message_when_data_empty(self, converter: OpenAIStreamConverter) -> None:
        """ERROR with no message uses a sensible default string."""
        conv = converter
        chunks = conv.convert(_ev(EventType.ERROR))

        assert chunks[0]["error"]["message"] == "An error occurred"

    def test_error_is_always_emitted_regardless_of_agent(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """ERROR from any agent (even sub-agent) is always terminal."""
        conv = converter
        chunks = conv.convert(_ev(EventType.ERROR, agent=SUB, message="crash"))

        assert _finish(chunks[0]) == "error"


# ---------------------------------------------------------------------------
# Reset behaviour
# ---------------------------------------------------------------------------


class TestReset:
    """reset() clears per-stream state while preserving configuration."""

    def test_reset_generates_new_completion_id(self, converter: OpenAIStreamConverter) -> None:
        """reset() creates a fresh completion id for the next stream."""
        conv = converter
        id_before = conv._completion_id  # noqa: SLF001
        conv.reset()

        assert conv._completion_id != id_before  # noqa: SLF001

    def test_reset_clears_role_state_so_role_is_sent_again(
        self, converter: OpenAIStreamConverter
    ) -> None:
        """After reset(), the first chunk of the new stream includes role='assistant'."""
        conv = converter
        conv.convert(_ev(EventType.TOKEN, text="first stream"))
        conv.reset()
        chunks = conv.convert(_ev(EventType.TOKEN, text="second stream"))

        assert _delta(chunks[0]).get("role") == "assistant"

    def test_reset_clears_open_tool_calls(self, converter: OpenAIStreamConverter) -> None:
        """reset() clears the pending TOOL_START frames so a stale TOOL_END is a no-op."""
        conv = converter
        conv.convert(_ev(EventType.TOOL_START, tool_name="t", tool_use_id="c", tool_input={}))
        assert conv._open_tool_calls  # noqa: SLF001
        conv.reset()

        assert conv._open_tool_calls == {}  # noqa: SLF001

    def test_reset_preserves_configuration(self, gpt4o_converter: OpenAIStreamConverter) -> None:
        """reset() does not alter model_label or other constructor config."""
        conv = gpt4o_converter
        conv.reset()
        chunks = conv.convert(_ev(EventType.TOKEN, text="x"))

        assert chunks[0]["model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# Model label
# ---------------------------------------------------------------------------


class TestModelLabel:
    """The model field in every chunk."""

    def test_model_defaults_to_entry_agent_name(
        self, entry_name_converter: OpenAIStreamConverter
    ) -> None:
        """Without model_label, 'model' equals entry_agent_name."""
        conv = entry_name_converter
        chunks = conv.convert(_ev(EventType.TOKEN, text="hi"))

        assert chunks[0]["model"] == AGENT

    def test_custom_model_label_overrides_entry_agent_name(
        self, gpt4o_converter: OpenAIStreamConverter
    ) -> None:
        """model_label='gpt-4o' is used instead of entry_agent_name."""
        conv = gpt4o_converter
        chunks = conv.convert(_ev(EventType.TOKEN, text="hi"))

        assert chunks[0]["model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# Unknown / unhandled events
# ---------------------------------------------------------------------------


class TestUnknownEvents:
    """Unknown event types are silently dropped."""

    def test_unknown_event_type_produces_no_chunks(self, converter: OpenAIStreamConverter) -> None:
        """Events with unrecognized type return an empty list."""
        conv = converter
        chunks = conv.convert(_ev("some_future_event_type", info="x"))

        assert chunks == []

    def test_agent_start_event_is_silently_dropped(self, converter: OpenAIStreamConverter) -> None:
        """AGENT_START is not handled and returns nothing."""
        conv = converter
        chunks = conv.convert(_ev(EventType.AGENT_START))

        assert chunks == []


# ---------------------------------------------------------------------------
# done_marker
# ---------------------------------------------------------------------------


class TestDoneMarker:
    """done_marker() returns the SSE stream terminator."""

    def test_done_marker_format(self, converter: OpenAIStreamConverter) -> None:
        """done_marker() returns the standard OpenAI SSE sentinel."""
        conv = converter

        assert conv.done_marker() == "data: [DONE]\n\n"
