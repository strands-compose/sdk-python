"""OpenAI streaming-chunk conversion for LibreChat / OpenWebUI compatibility.

Converts :class:`~strands_compose.wire.StreamEvent` objects into
OpenAI ``chat.completion.chunk`` dicts suitable for Server-Sent Events.

**Key structural rules** enforced by the OpenAI SDK and widely adopted by
compatible providers (Together, Groq, DeepSeek, vLLM, …):

1.  Every chunk shares the same ``id`` and ``created`` within one
    completion.  ``model`` echoes the model name.
2.  ``choices`` is a list; each entry has ``index``, ``delta`` (partial
    content), and ``finish_reason`` (``null`` until the last chunk).
3.  Text tokens -> ``delta.content``.
4.  Tool calls -> ``delta.tool_calls`` list of ``{index, id, type,
    function: {name, arguments}}`` fragments.  Since strands provides
    the complete tool input at call time, we emit **one** chunk with the
    full name + serialised arguments.
5.  Reasoning / chain-of-thought -> ``delta.reasoning_content``
    (DeepSeek convention; supported by most OpenAI-compatible clients).
6.  The final content chunk always has ``finish_reason: "stop"``.
    The ``"tool_calls"`` value is intentionally not used here — tool
    invocations are already complete when the COMPLETE event fires.
    OpenAI-compatible clients (LibreChat, OpenWebUI, Continue.dev)
    interpret ``"tool_calls"`` as a signal to expect tool outputs,
    which would cause an infinite loop.
7.  ``usage`` (``prompt_tokens``, ``completion_tokens``,
    ``total_tokens``) appears on the last chunk when the provider
    supports ``stream_options: {include_usage: true}``.

Multi-agent events (NODE_START, NODE_STOP, MULTIAGENT_COMPLETE) have
no OpenAI equivalent.  They are wrapped in a ``_strands_event``
extension field so consumers can still observe orchestration flow.

Usage::

    converter = OpenAIStreamConverter()
    for event in events:
        for chunk in converter.convert(event):
            yield f"data: {json.dumps(chunk)}\\n\\n"
    yield "data: [DONE]\\n\\n"
"""

from __future__ import annotations

import json
import time as _time
import uuid
from typing import TYPE_CHECKING, Any

from ..types import EventType
from .base import StreamConverter

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..wire import StreamEvent


class OpenAIStreamConverter(StreamConverter):
    """Stateful converter from StreamEvent to OpenAI ``chat.completion.chunk`` dicts."""

    def __init__(self, completion_id: str | None = None) -> None:
        """Initialize the OpenAIStreamConverter.

        Tracks state across a single completion stream to ensure:

        - Consistent ``id`` and ``created`` across all chunks.
        - ``role: "assistant"`` emitted only on the first content chunk.
        - ``finish_reason`` is always ``"stop"`` on the COMPLETE chunk.
        - Tool call index tracking for multi-tool responses.
        - ``_has_tool_calls`` is set to ``True`` whenever a TOOL_START
          event is seen (useful for logging/metrics).

        Args:
            completion_id: Optional completion ID. If not provided, a random
                ``chatcmpl-*`` ID is generated.
        """
        self._completion_id = completion_id or f"chatcmpl-{uuid.uuid4().hex[:24]}"
        self._created = int(_time.time())
        self._sent_role = False
        self._has_tool_calls = False
        self._tool_call_index = 0
        self._handlers: dict[str, Callable[[StreamEvent], list[dict[str, Any]]]] = {
            EventType.TOKEN: self._handle_token,
            EventType.REASONING: self._handle_reasoning,
            EventType.TOOL_START: self._handle_tool_start,
            EventType.TOOL_END: self._handle_tool_end,
            EventType.COMPLETE: self._handle_complete,
            EventType.ERROR: self._handle_error,
        }

    def _base(self, agent_name: str) -> dict[str, Any]:
        """Shared skeleton for every ``chat.completion.chunk``."""
        return {
            "id": self._completion_id,
            "object": "chat.completion.chunk",
            "created": self._created,
            "model": agent_name,
        }

    def convert(self, event: StreamEvent) -> list[dict[str, Any]]:
        """Convert a StreamEvent to OpenAI chunk(s).

        Args:
            event: The StreamEvent to convert.

        Returns:
            A list of ``chat.completion.chunk`` dicts (possibly empty).
        """
        handler = self._handlers.get(event.type)
        if handler is not None:
            return handler(event)

        return [self._passthrough(event)]

    # -- Per-event-type handlers -----------------------------------------------

    def _handle_token(self, event: StreamEvent) -> list[dict[str, Any]]:
        """TOKEN -> ``delta.content``."""
        chunk = self._base(event.agent_name)
        delta: dict[str, Any] = {"content": event.data.get("text", "")}
        if not self._sent_role:
            delta["role"] = "assistant"
            self._sent_role = True
        chunk["choices"] = [{"index": 0, "delta": delta, "finish_reason": None}]
        return [chunk]

    def _handle_reasoning(self, event: StreamEvent) -> list[dict[str, Any]]:
        """REASONING -> ``delta.reasoning_content``."""
        chunk = self._base(event.agent_name)
        delta: dict[str, Any] = {"reasoning_content": event.data.get("text", "")}
        if not self._sent_role:
            delta["role"] = "assistant"
            self._sent_role = True
        chunk["choices"] = [{"index": 0, "delta": delta, "finish_reason": None}]
        return [chunk]

    def _handle_tool_start(self, event: StreamEvent) -> list[dict[str, Any]]:
        """TOOL_START -> ``delta.tool_calls``.

        Emits a single chunk with the complete function name and
        JSON-serialised arguments.
        """
        self._has_tool_calls = True
        tool_use_id = event.data.get("tool_use_id") or f"call_{uuid.uuid4().hex[:24]}"
        chunk = self._base(event.agent_name)
        delta: dict[str, Any] = {
            "tool_calls": [
                {
                    "index": self._tool_call_index,
                    "id": tool_use_id,
                    "type": "function",
                    "function": {
                        "name": event.data.get("tool_name", ""),
                        "arguments": json.dumps(event.data.get("tool_input", {})),
                    },
                }
            ],
        }
        if not self._sent_role:
            delta["role"] = "assistant"
            self._sent_role = True
        chunk["choices"] = [{"index": 0, "delta": delta, "finish_reason": None}]
        self._tool_call_index += 1
        return [chunk]

    def _handle_tool_end(self, event: StreamEvent) -> list[dict[str, Any]]:
        """TOOL_END -> passthrough in ``_strands_event`` extension.

        OpenAI's streaming protocol has no tool-result chunk — results
        are submitted by the caller in the next request.  We pass
        through the event data in the ``_strands_event`` extension field
        so clients that understand it can observe tool results.
        """
        return [self._passthrough(event)]

    def _handle_error(self, event: StreamEvent) -> list[dict[str, Any]]:
        """ERROR -> ``finish_reason: "error"`` + top-level ``error``."""
        chunk = self._base(event.agent_name)
        chunk["choices"] = [{"index": 0, "delta": {}, "finish_reason": "error"}]
        chunk["error"] = {
            "message": event.data.get("message", "An error occurred"),
            "type": "agent_error",
        }
        return [chunk]

    def _handle_complete(self, event: StreamEvent) -> list[dict[str, Any]]:
        """COMPLETE -> final chunk with ``finish_reason: "stop"`` and ``usage``.

        Always emits ``finish_reason: "stop"``.  Tool invocations are
        complete by the time this event fires; using ``"tool_calls"``
        would signal OpenAI-compatible clients to expect pending tool
        results and cause an infinite loop.

        ``_has_tool_calls`` is still tracked and available for metrics.
        """
        usage_in = event.data.get("usage", {})
        finish_reason = "stop"
        chunk = self._base(event.agent_name)
        chunk["choices"] = [{"index": 0, "delta": {}, "finish_reason": finish_reason}]
        chunk["usage"] = {
            "prompt_tokens": usage_in.get("input_tokens", 0),
            "completion_tokens": usage_in.get("output_tokens", 0),
            "total_tokens": usage_in.get("total_tokens", 0),
        }
        return [chunk]

    def done_marker(self) -> str:
        """Return the OpenAI SSE stream terminator.

        Returns:
            The 'data: [DONE]\\n\\n' sentinel string.
        """
        return "data: [DONE]\n\n"

    def _passthrough(self, event: StreamEvent) -> dict[str, Any]:
        """Wrap unknown/multi-agent events in ``_strands_event`` extension."""
        chunk = self._base(event.agent_name)
        chunk["choices"] = [{"index": 0, "delta": {}, "finish_reason": None}]
        chunk["_strands_event"] = event.asdict()
        return chunk
