"""Regression tests for OpenAIStreamConverter.

Specifically guards the fix for B1: finish_reason must always be "stop" on the
COMPLETE event, regardless of whether tool calls occurred during the stream.
"""

from __future__ import annotations

import pytest

from strands_compose.converters.openai import OpenAIStreamConverter
from strands_compose.types import EventType
from strands_compose.wire import StreamEvent

AGENT = "test-agent"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(type_: str, **data: object) -> StreamEvent:
    """Build a StreamEvent with the given type and payload."""
    return StreamEvent(type=type_, agent_name=AGENT, data=dict(data))


def _finish_reason(chunks: list[dict]) -> str | None:
    """Return the finish_reason from the first choice of the first chunk."""
    return chunks[0]["choices"][0]["finish_reason"]


# ---------------------------------------------------------------------------
# finish_reason regression tests (B1)
# ---------------------------------------------------------------------------


class TestFinishReasonAlwaysStop:
    """finish_reason must be 'stop' on COMPLETE regardless of tool usage."""

    def test_finish_reason_is_stop_without_tool_calls(self) -> None:
        """COMPLETE after a plain token stream emits finish_reason 'stop'."""
        conv = OpenAIStreamConverter()
        conv.convert(_event(EventType.TOKEN, text="hello"))
        chunks = conv.convert(_event(EventType.COMPLETE, usage={}))

        assert len(chunks) == 1
        assert _finish_reason(chunks) == "stop"

    def test_finish_reason_is_stop_after_tool_calls(self) -> None:
        """COMPLETE after TOOL_START/TOOL_END must still emit finish_reason 'stop'.

        Regression: the old code returned 'tool_calls' here, which caused
        OpenAI-compatible clients (LibreChat, OpenWebUI, Continue.dev) to
        interpret the completion as a pending tool-execution step and loop
        forever.
        """
        conv = OpenAIStreamConverter()
        conv.convert(
            _event(
                EventType.TOOL_START,
                tool_name="search",
                tool_use_id="call_abc",
                tool_input={"q": "hello"},
            )
        )
        conv.convert(_event(EventType.TOOL_END, tool_use_id="call_abc", result="ok"))
        chunks = conv.convert(_event(EventType.COMPLETE, usage={}))

        assert len(chunks) == 1
        assert _finish_reason(chunks) != "tool_calls", (
            "finish_reason must never be 'tool_calls' on COMPLETE — that "
            "causes clients to loop expecting pending tool results"
        )
        assert _finish_reason(chunks) == "stop"

    def test_finish_reason_is_stop_after_multiple_tool_calls(self) -> None:
        """COMPLETE after multiple TOOL_START events still emits 'stop'."""
        conv = OpenAIStreamConverter()
        for i in range(3):
            conv.convert(
                _event(
                    EventType.TOOL_START,
                    tool_name=f"tool_{i}",
                    tool_use_id=f"call_{i}",
                    tool_input={},
                )
            )
        chunks = conv.convert(_event(EventType.COMPLETE, usage={}))

        assert _finish_reason(chunks) == "stop"


# ---------------------------------------------------------------------------
# _has_tool_calls tracking
# ---------------------------------------------------------------------------


class TestHasToolCallsTracking:
    """_has_tool_calls is still set correctly — it is used for metrics."""

    def test_has_tool_calls_false_initially(self) -> None:
        """_has_tool_calls starts as False on a fresh converter."""
        conv = OpenAIStreamConverter()
        assert conv._has_tool_calls is False  # noqa: SLF001

    def test_has_tool_calls_set_true_on_tool_start(self) -> None:
        """_has_tool_calls is set to True when a TOOL_START event is processed."""
        conv = OpenAIStreamConverter()
        assert conv._has_tool_calls is False  # noqa: SLF001

        conv.convert(
            _event(
                EventType.TOOL_START,
                tool_name="do_thing",
                tool_use_id="call_x",
                tool_input={},
            )
        )

        assert conv._has_tool_calls is True  # noqa: SLF001

    def test_has_tool_calls_remains_false_without_tool_start(self) -> None:
        """_has_tool_calls stays False when no TOOL_START events are seen."""
        conv = OpenAIStreamConverter()
        conv.convert(_event(EventType.TOKEN, text="hi"))
        conv.convert(_event(EventType.COMPLETE, usage={}))

        assert conv._has_tool_calls is False  # noqa: SLF001

    def test_has_tool_calls_true_persists_through_complete(self) -> None:
        """_has_tool_calls remains True after the COMPLETE event fires."""
        conv = OpenAIStreamConverter()
        conv.convert(_event(EventType.TOOL_START, tool_name="t", tool_use_id="c", tool_input={}))
        conv.convert(_event(EventType.COMPLETE, usage={}))

        assert conv._has_tool_calls is True  # noqa: SLF001


# ---------------------------------------------------------------------------
# COMPLETE chunk shape
# ---------------------------------------------------------------------------


class TestCompleteChunkShape:
    """Verify the overall shape of the COMPLETE chunk."""

    def test_complete_chunk_includes_usage(self) -> None:
        """COMPLETE chunk maps usage fields from strands to OpenAI names."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(
            _event(
                EventType.COMPLETE,
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            )
        )

        assert len(chunks) == 1
        usage = chunks[0]["usage"]
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 20
        assert usage["total_tokens"] == 30

    def test_complete_chunk_usage_defaults_to_zero_when_missing(self) -> None:
        """Missing usage fields default to 0, not KeyError."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.COMPLETE, usage={}))

        usage = chunks[0]["usage"]
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0

    def test_complete_chunk_delta_is_empty(self) -> None:
        """The delta on the COMPLETE chunk is an empty dict."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.COMPLETE, usage={}))

        assert chunks[0]["choices"][0]["delta"] == {}

    @pytest.mark.parametrize(
        ("field",),
        [("id",), ("object",), ("created",), ("model",), ("choices",), ("usage",)],
    )
    def test_complete_chunk_has_required_openai_fields(self, field: str) -> None:
        """Each required OpenAI chunk field is present on the COMPLETE chunk."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.COMPLETE, usage={}))
        assert field in chunks[0]


# ---------------------------------------------------------------------------
# REASONING event conversion (R1 — coverage gap)
# ---------------------------------------------------------------------------


class TestReasoningEvent:
    """OpenAIStreamConverter REASONING -> delta.reasoning_content."""

    def test_reasoning_produces_reasoning_content_delta(self) -> None:
        """REASONING event produces a chunk with delta.reasoning_content."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.REASONING, text="thinking about it"))

        assert len(chunks) == 1
        delta = chunks[0]["choices"][0]["delta"]
        assert delta["reasoning_content"] == "thinking about it"
        assert chunks[0]["choices"][0]["finish_reason"] is None

    def test_reasoning_first_chunk_includes_role(self) -> None:
        """First REASONING chunk includes role='assistant'."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.REASONING, text="step 1"))

        delta = chunks[0]["choices"][0]["delta"]
        assert delta["role"] == "assistant"

    def test_reasoning_subsequent_chunk_no_role(self) -> None:
        """Second REASONING chunk does not include role."""
        conv = OpenAIStreamConverter()
        conv.convert(_event(EventType.REASONING, text="step 1"))
        chunks = conv.convert(_event(EventType.REASONING, text="step 2"))

        delta = chunks[0]["choices"][0]["delta"]
        assert "role" not in delta

    def test_reasoning_then_token_role_sent_once(self) -> None:
        """role='assistant' is sent only on the first content chunk (REASONING or TOKEN)."""
        conv = OpenAIStreamConverter()
        conv.convert(_event(EventType.REASONING, text="hmm"))
        chunks = conv.convert(_event(EventType.TOKEN, text="answer"))

        # TOKEN chunk should NOT have role since it was sent with REASONING
        delta = chunks[0]["choices"][0]["delta"]
        assert "role" not in delta

    def test_reasoning_empty_text_defaults(self) -> None:
        """REASONING with missing text defaults to empty string."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.REASONING))

        assert chunks[0]["choices"][0]["delta"]["reasoning_content"] == ""


# ---------------------------------------------------------------------------
# ERROR event conversion (R1 — coverage gap)
# ---------------------------------------------------------------------------


class TestErrorEvent:
    """OpenAIStreamConverter ERROR -> finish_reason 'error' + error field."""

    def test_error_produces_error_finish_reason(self) -> None:
        """ERROR event produces finish_reason 'error'."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.ERROR, message="Token expired"))

        assert len(chunks) == 1
        assert chunks[0]["choices"][0]["finish_reason"] == "error"
        assert chunks[0]["choices"][0]["delta"] == {}

    def test_error_includes_error_field(self) -> None:
        """ERROR event includes top-level 'error' with message and type."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.ERROR, message="Model overloaded"))

        error = chunks[0]["error"]
        assert error["message"] == "Model overloaded"
        assert error["type"] == "agent_error"

    def test_error_default_message(self) -> None:
        """ERROR event uses default message when none provided."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.ERROR))

        assert chunks[0]["error"]["message"] == "An error occurred"

    def test_error_has_standard_chunk_fields(self) -> None:
        """ERROR chunk has id, object, created, model like any other chunk."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.ERROR, message="fail"))

        chunk = chunks[0]
        assert "id" in chunk
        assert chunk["object"] == "chat.completion.chunk"
        assert "created" in chunk
        assert chunk["model"] == AGENT


# ---------------------------------------------------------------------------
# AGENT_START / passthrough event conversion (R1 — coverage gap)
# ---------------------------------------------------------------------------


class TestPassthroughEvents:
    """Unknown event types (incl. AGENT_START) use _strands_event extension."""

    def test_agent_start_wrapped_in_strands_event(self) -> None:
        """AGENT_START is wrapped in _strands_event extension field."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.AGENT_START))

        assert len(chunks) == 1
        chunk = chunks[0]
        assert "_strands_event" in chunk
        assert chunk["_strands_event"]["type"] == EventType.AGENT_START
        assert chunk["choices"][0]["finish_reason"] is None

    def test_node_start_wrapped_in_strands_event(self) -> None:
        """NODE_START is wrapped in _strands_event extension field."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.NODE_START, node_id="researcher"))

        assert "_strands_event" in chunks[0]
        assert chunks[0]["_strands_event"]["data"]["node_id"] == "researcher"

    def test_tool_end_wrapped_in_strands_event(self) -> None:
        """TOOL_END is wrapped in _strands_event extension (no OpenAI equivalent)."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.TOOL_END, tool_use_id="call_1", result="ok"))

        assert "_strands_event" in chunks[0]
        assert chunks[0]["_strands_event"]["type"] == EventType.TOOL_END

    def test_multiagent_complete_wrapped_in_strands_event(self) -> None:
        """MULTIAGENT_COMPLETE is wrapped in _strands_event."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.MULTIAGENT_COMPLETE, multiagent_type="swarm"))

        assert "_strands_event" in chunks[0]

    def test_custom_unknown_event_wrapped_in_strands_event(self) -> None:
        """Completely unknown event type is also wrapped in _strands_event."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event("custom_event_type", info="x"))

        assert "_strands_event" in chunks[0]
        assert chunks[0]["_strands_event"]["type"] == "custom_event_type"


# ---------------------------------------------------------------------------
# OpenAI API schema validation (R7)
# ---------------------------------------------------------------------------


class TestOpenAISchemaContract:
    """Validate output chunks conform to OpenAI chat.completion.chunk schema."""

    REQUIRED_CHUNK_FIELDS = {"id", "object", "created", "model", "choices"}

    def _validate_chunk(self, chunk: dict) -> None:
        """Assert a chunk has all required OpenAI fields and correct types."""
        for field in self.REQUIRED_CHUNK_FIELDS:
            assert field in chunk, f"Missing required field: {field}"
        assert chunk["object"] == "chat.completion.chunk"
        assert isinstance(chunk["id"], str)
        assert chunk["id"].startswith("chatcmpl-")
        assert isinstance(chunk["created"], int)
        assert isinstance(chunk["model"], str)
        assert isinstance(chunk["choices"], list)
        assert len(chunk["choices"]) >= 1
        choice = chunk["choices"][0]
        assert "index" in choice
        assert "delta" in choice
        assert "finish_reason" in choice

    def test_token_chunk_schema(self) -> None:
        """TOKEN chunk conforms to OpenAI schema."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.TOKEN, text="hello"))
        self._validate_chunk(chunks[0])
        assert "content" in chunks[0]["choices"][0]["delta"]

    def test_reasoning_chunk_schema(self) -> None:
        """REASONING chunk conforms to OpenAI schema."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.REASONING, text="think"))
        self._validate_chunk(chunks[0])
        assert "reasoning_content" in chunks[0]["choices"][0]["delta"]

    def test_tool_start_chunk_schema(self) -> None:
        """TOOL_START chunk conforms to OpenAI schema."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(
            _event(
                EventType.TOOL_START,
                tool_name="search",
                tool_use_id="call_1",
                tool_input={"q": "test"},
            )
        )
        self._validate_chunk(chunks[0])
        delta = chunks[0]["choices"][0]["delta"]
        assert "tool_calls" in delta
        tc = delta["tool_calls"][0]
        assert "id" in tc
        assert tc["type"] == "function"
        assert "name" in tc["function"]
        assert "arguments" in tc["function"]

    def test_complete_chunk_schema(self) -> None:
        """COMPLETE chunk conforms to OpenAI schema with usage."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(
            _event(EventType.COMPLETE, usage={"input_tokens": 5, "output_tokens": 10})
        )
        self._validate_chunk(chunks[0])
        assert "usage" in chunks[0]
        usage = chunks[0]["usage"]
        assert "prompt_tokens" in usage
        assert "completion_tokens" in usage
        assert "total_tokens" in usage

    def test_error_chunk_schema(self) -> None:
        """ERROR chunk conforms to OpenAI schema."""
        conv = OpenAIStreamConverter()
        chunks = conv.convert(_event(EventType.ERROR, message="fail"))
        self._validate_chunk(chunks[0])
        assert "error" in chunks[0]

    def test_completion_id_consistent_across_chunks(self) -> None:
        """All chunks in a stream share the same completion id."""
        conv = OpenAIStreamConverter()
        c1 = conv.convert(_event(EventType.TOKEN, text="a"))
        c2 = conv.convert(_event(EventType.TOKEN, text="b"))
        c3 = conv.convert(_event(EventType.COMPLETE, usage={}))

        ids = {c1[0]["id"], c2[0]["id"], c3[0]["id"]}
        assert len(ids) == 1, "All chunks must share the same completion id"

    def test_custom_completion_id(self) -> None:
        """Custom completion_id is used when provided."""
        conv = OpenAIStreamConverter(completion_id="chatcmpl-custom123")
        chunks = conv.convert(_event(EventType.TOKEN, text="test"))
        assert chunks[0]["id"] == "chatcmpl-custom123"

    def test_done_marker_format(self) -> None:
        """done_marker() returns the standard OpenAI SSE sentinel."""
        conv = OpenAIStreamConverter()
        assert conv.done_marker() == "data: [DONE]\n\n"
