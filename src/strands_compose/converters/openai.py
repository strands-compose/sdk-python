from __future__ import annotations

import html
import json
import time as _time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from ..types import EventType
from .base import StreamConverter

if TYPE_CHECKING:
    from ..wire import StreamEvent


@dataclass
class _ToolCallFrame:
    """Tracks one open tool call or node for the details-block lifecycle."""

    call_id: str
    name: str
    arguments_json: str
    # Populated by TOOL_END / NODE_STOP
    result_text: str | None = field(default=None)


class OpenAIStreamConverter(StreamConverter):
    """Stateful converter from :class:`~strands_compose.wire.StreamEvent` to OpenAI ``chat.completion.chunk`` dicts.

    Targets Open WebUI and LibreChat.  Translates strands events into the
    OpenAI Chat Completions streaming protocol (v1) with reasoning extensions
    from DeepSeek (``reasoning_content``) and OpenRouter (``reasoning``).

    Single-use per stream.  Call :meth:`reset` to reuse across requests.
    """

    def __init__(
        self,
        *,
        entry_agent_name: str,
        model_label: str | None = None,
        completion_id: str | None = None,
        reasoning_field_mode: Literal["both", "deepseek", "openrouter", "none"] = "both",
        tool_result_render: Literal["details_block", "none"] = "details_block",
        emit_usage_chunk: bool = False,
        verbosity: Literal["compact", "narrate"] = "compact",
    ) -> None:
        """Initialize the OpenAIStreamConverter.

        Args:
            entry_agent_name: Name of the agent that owns the user-visible turn.
                TOKEN and REASONING from all other agents are suppressed.
                NODE_START/NODE_STOP from this agent surface sub-agents as
                ``<details>`` blocks alongside tool calls.
            model_label: Value for every chunk's ``model`` field.  Defaults to
                ``entry_agent_name``.  Pass the ``model`` from the incoming
                request body so the response echoes it faithfully.
            completion_id: Fixed id for the whole stream.  Defaults to a fresh
                ``chatcmpl-<hex24>`` on each instantiation.
            reasoning_field_mode: Which ``delta`` field(s) carry reasoning.

                - ``"both"`` (default): ``reasoning_content`` (Open WebUI /
                  DeepSeek) **and** ``reasoning`` (LibreChat / OpenRouter).
                - ``"deepseek"``: only ``reasoning_content``.
                - ``"openrouter"``: only ``reasoning``.
                - ``"none"``: reasoning dropped from the stream.
            tool_result_render: How tool calls and results are surfaced.

                - ``"details_block"`` (default): a single completed
                  ``<details type="tool_calls" done="true">`` block emitted on
                  TOOL_END / NODE_STOP, carrying the call inputs as HTML
                  attributes and the result as the body. No native
                  ``delta.tool_calls`` chunks are produced because strands has
                  already executed the tool by the time the stream emits it;
                  emitting native deltas without a closing
                  ``finish_reason: "tool_calls"`` only confuses clients into
                  looping on the response.
                - ``"none"``: tool calls and results are not surfaced at all.
            emit_usage_chunk: When ``True``, deliver usage as a separate trailing
                chunk with ``choices: []`` matching ``stream_options: {include_usage: true}``.
                When ``False`` (default), usage is stapled to the ``finish_reason`` chunk.
            verbosity: ``"compact"`` (default) streams only entry-agent tokens.
                ``"narrate"`` also streams sub-agent tokens inside the active
                node's ``<details>`` body.
        """
        self._entry_agent_name = entry_agent_name
        self._model_label: str = model_label if model_label is not None else entry_agent_name
        self._completion_id = completion_id or f"chatcmpl-{uuid.uuid4().hex[:24]}"
        self._created = int(_time.time())
        self._reasoning_field_mode = reasoning_field_mode
        self._tool_result_render = tool_result_render
        self._emit_usage_chunk = emit_usage_chunk
        self._verbosity = verbosity

        # Mutable stream state — reset on each call to reset()
        self._sent_role = False
        self._open_tool_calls: dict[str, _ToolCallFrame] = {}
        self._open_node_frames: dict[str, _ToolCallFrame] = {}
        self._reasoning_tokens: int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def convert(self, event: StreamEvent) -> list[dict[str, Any]]:
        """Convert one :class:`~strands_compose.wire.StreamEvent` into OpenAI chunk(s).

        Args:
            event: The event to convert.

        Returns:
            A list of ``chat.completion.chunk`` dicts (possibly empty).
            The transport layer is responsible for ``data: {json}\\n\\n`` framing.
        """
        is_entry = event.agent_name == self._entry_agent_name

        dispatch: dict[str, Any] = {
            EventType.TOKEN: self._handle_token,
            EventType.REASONING: self._handle_reasoning,
            EventType.TOOL_START: self._handle_tool_start,
            EventType.TOOL_END: self._handle_tool_end,
            EventType.AGENT_COMPLETE: self._handle_complete,
            EventType.MULTIAGENT_COMPLETE: self._handle_multiagent_complete,
            EventType.ERROR: self._handle_error,
            EventType.NODE_START: self._handle_node_start,
            EventType.NODE_STOP: self._handle_node_stop,
        }

        handler = dispatch.get(event.type)
        if handler is not None:
            return handler(event, is_entry)
        return []

    def done_marker(self) -> str:
        """Return the OpenAI SSE stream terminator.

        Returns:
            The ``data: [DONE]\\n\\n`` sentinel string.
        """
        return "data: [DONE]\n\n"

    def reset(self) -> None:
        """Reset all mutable stream state for reuse across requests.

        Preserves constructor configuration and regenerates ``completion_id``
        and ``created`` for the new stream.
        """
        self._completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        self._created = int(_time.time())
        self._sent_role = False
        self._open_tool_calls = {}
        self._open_node_frames = {}
        self._reasoning_tokens = 0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _base(self) -> dict[str, Any]:
        """Shared envelope skeleton for every ``chat.completion.chunk``."""
        return {
            "id": self._completion_id,
            "object": "chat.completion.chunk",
            "created": self._created,
            "model": self._model_label,
        }

    def _maybe_role(self) -> dict[str, Any]:
        """Return ``{"role": "assistant"}`` once, then an empty dict."""
        if not self._sent_role:
            self._sent_role = True
            return {"role": "assistant"}
        return {}

    def _content_chunk(self, content: str) -> dict[str, Any]:
        """Build a single ``delta.content`` chunk."""
        chunk = self._base()
        chunk["choices"] = [
            {"index": 0, "delta": {**self._maybe_role(), "content": content}, "finish_reason": None}
        ]
        return chunk

    def _terminal_chunks(
        self,
        usage_in: dict[str, Any],
        *,
        error_msg: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build the terminal finish_reason chunk and optional trailing usage chunk.

        Always emits ``finish_reason: "stop"``.  ``"tool_calls"`` is never used
        because by the time AGENT_COMPLETE fires every tool has already run inside the
        strands loop — emitting ``"tool_calls"`` would cause clients to wait for
        results that never arrive.
        """
        finish_chunk = self._base()
        if error_msg is not None:
            finish_chunk["choices"] = [{"index": 0, "delta": {}, "finish_reason": "error"}]
            finish_chunk["error"] = {"message": error_msg, "type": "agent_error"}
            finish_chunk["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            return [finish_chunk]

        finish_chunk["choices"] = [{"index": 0, "delta": {}, "finish_reason": "stop"}]

        usage_payload: dict[str, Any] = {
            "prompt_tokens": usage_in.get("input_tokens", 0),
            "completion_tokens": usage_in.get("output_tokens", 0),
            "total_tokens": usage_in.get("total_tokens", 0),
        }
        cached_tokens = usage_in.get("cache_read_input_tokens", 0)
        if cached_tokens:
            usage_payload["prompt_tokens_details"] = {"cached_tokens": cached_tokens}
        if self._reasoning_tokens > 0:
            usage_payload["completion_tokens_details"] = {
                "reasoning_tokens": self._reasoning_tokens
            }

        if self._emit_usage_chunk:
            usage_chunk = self._base()
            usage_chunk["choices"] = []
            usage_chunk["usage"] = usage_payload
            return [finish_chunk, usage_chunk]

        finish_chunk["usage"] = usage_payload
        return [finish_chunk]

    # ── Details-block helpers ─────────────────────────────────────────────────

    @staticmethod
    def _html_attr(value: str) -> str:
        """HTML-escape a string for use as an attribute value."""
        return html.escape(value, quote=True)

    def _details_closer(
        self,
        call_id: str,
        name: str,
        arguments_json: str,
        result_text: str | None,
    ) -> str:
        """Return the completed ``<details>`` HTML block, replacing the opener."""
        escaped_args = self._html_attr(arguments_json)
        escaped_name = self._html_attr(name)
        body = html.escape(result_text) if result_text else ""
        return (
            f'<details type="tool_calls" done="true" id="{call_id}"'
            f' name="{escaped_name}" arguments="{escaped_args}">\n'
            f"<summary>Tool: {escaped_name}</summary>\n"
            f"{body}\n"
            f"</details>\n"
        )

    # ── Per-event handlers ────────────────────────────────────────────────────

    def _handle_token(self, event: StreamEvent, is_entry: bool) -> list[dict[str, Any]]:
        """TOKEN → ``delta.content`` for entry agent; suppressed for sub-agents."""
        if not is_entry:
            if self._verbosity == "narrate" and self._open_node_frames:
                return [self._content_chunk(event.data.get("text", ""))]
            return []

        chunk = self._base()
        chunk["choices"] = [
            {
                "index": 0,
                "delta": {**self._maybe_role(), "content": event.data.get("text", "")},
                "finish_reason": None,
            }
        ]
        return [chunk]

    def _handle_reasoning(self, event: StreamEvent, is_entry: bool) -> list[dict[str, Any]]:
        """REASONING → reasoning delta fields for entry agent; suppressed for sub-agents."""
        if not is_entry:
            return []

        text = event.data.get("text", "")
        self._reasoning_tokens += max(1, len(text) // 4)

        delta: dict[str, Any] = {**self._maybe_role()}
        if self._reasoning_field_mode in ("both", "deepseek"):
            delta["reasoning_content"] = text
        if self._reasoning_field_mode in ("both", "openrouter"):
            delta["reasoning"] = text

        # Nothing to emit when mode is "none" (only role key present or empty)
        if set(delta.keys()) <= {"role"}:
            return []

        chunk = self._base()
        chunk["choices"] = [{"index": 0, "delta": delta, "finish_reason": None}]
        return [chunk]

    def _handle_tool_start(self, event: StreamEvent, is_entry: bool) -> list[dict[str, Any]]:
        """TOOL_START → bookkeeping only; no chunks are emitted.

        The completed tool call is rendered by :meth:`_handle_tool_end` as a
        single ``<details done="true">`` block. No native ``delta.tool_calls``
        chunk is produced because strands has already executed the tool by the
        time the stream surfaces it.
        """
        if not is_entry:
            return []

        tool_use_id = event.data.get("tool_use_id") or f"call_{uuid.uuid4().hex[:24]}"
        tool_name = event.data.get("tool_name", "")
        arguments_json = json.dumps(event.data.get("tool_input", {}))

        self._open_tool_calls[tool_use_id] = _ToolCallFrame(
            call_id=tool_use_id,
            name=tool_name,
            arguments_json=arguments_json,
        )
        return []

    def _handle_tool_end(self, event: StreamEvent, is_entry: bool) -> list[dict[str, Any]]:
        """TOOL_END → ``<details done="true">`` closer, or silent."""
        if not is_entry:
            return []

        frame = self._open_tool_calls.pop(event.data.get("tool_use_id", ""), None)
        if self._tool_result_render == "details_block" and frame is not None:
            return [
                self._content_chunk(
                    self._details_closer(
                        frame.call_id,
                        frame.name,
                        frame.arguments_json,
                        event.data.get("tool_result"),
                    )
                )
            ]
        return []

    def _handle_node_start(self, event: StreamEvent, is_entry: bool) -> list[dict[str, Any]]:
        """NODE_START → bookkeeping only; the completed node renders at NODE_STOP."""
        if not is_entry:
            return []

        node_id = event.data.get("node_id", "")
        if node_id in self._open_node_frames:
            return []

        call_id = f"call_{uuid.uuid4().hex[:16]}"
        self._open_node_frames[node_id] = _ToolCallFrame(
            call_id=call_id,
            name=node_id,
            arguments_json="{}",
        )
        return []

    def _handle_node_stop(self, event: StreamEvent, is_entry: bool) -> list[dict[str, Any]]:
        """NODE_STOP → ``<details done="true">`` closer for the sub-agent node."""
        if not is_entry:
            return []

        frame = self._open_node_frames.pop(event.data.get("node_id", ""), None)
        if self._tool_result_render == "details_block" and frame is not None:
            return [
                self._content_chunk(
                    self._details_closer(
                        frame.call_id, frame.name, frame.arguments_json, frame.result_text
                    )
                )
            ]
        return []

    def _handle_complete(self, event: StreamEvent, is_entry: bool) -> list[dict[str, Any]]:
        """AGENT_COMPLETE → terminal chunks for entry agent; silent for sub-agents."""
        if not is_entry:
            return []
        return self._terminal_chunks(event.data.get("usage", {}))

    def _handle_multiagent_complete(
        self, event: StreamEvent, is_entry: bool
    ) -> list[dict[str, Any]]:
        """MULTIAGENT_COMPLETE → terminal chunks; silent for sub-orchestrations."""
        if not is_entry:
            return []
        return self._terminal_chunks(event.data.get("usage", {}))

    def _handle_error(self, event: StreamEvent, is_entry: bool) -> list[dict[str, Any]]:
        """ERROR → ``finish_reason: "error"`` terminal chunk."""
        return self._terminal_chunks({}, error_msg=event.data.get("message", "An error occurred"))
