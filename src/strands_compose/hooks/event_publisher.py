"""EventPublisher hook for streaming agent activities to external consumers.

Key Features:
    - Unified single-agent and multi-agent event publishing
    - Safe callback wrapping that logs instead of propagating exceptions
    - Longest-prefix tool label resolution for display names
    - Callback handler factory for TOKEN, REASONING, and HANDOFF events
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Callable
from typing import Any

from strands.hooks import HookProvider, HookRegistry

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from strands.hooks.events import (
    AfterInvocationEvent,
    AfterModelCallEvent,
    AfterMultiAgentInvocationEvent,
    AfterNodeCallEvent,
    AfterToolCallEvent,
    BeforeInvocationEvent,
    BeforeMultiAgentInvocationEvent,
    BeforeNodeCallEvent,
    BeforeToolCallEvent,
)

from ..types import EventType, StreamEvent

logger = logging.getLogger(__name__)

EventCallback = Callable[[StreamEvent], None]

_MAX_RESULT_LEN = 600


# ============================================================================
# Helpers
# ============================================================================


def _extract_result_text(result: Any, max_len: int = _MAX_RESULT_LEN) -> str | None:
    """Extract a plain-text summary from a strands tool result (for streaming TOOL_END)."""
    if result is None:
        return None
    parts: list[str] = []
    for block in result.get("content", []):
        if "text" in block:
            parts.append(block["text"])
        elif "json" in block:
            parts.append(str(block["json"]))
    raw = "\n".join(parts)
    if not raw:
        return None
    return raw[:max_len] + "..." if len(raw) > max_len else raw


def _resolve_tool_label(
    tool_name: str,
    labels: dict[str, str] | None = None,
) -> str | None:
    """Resolve a tool name to a display label via exact or longest-prefix match."""
    if not labels:
        return None
    if tool_name in labels:
        return labels[tool_name]
    best_match = None
    best_length = 0
    for prefix, label in labels.items():
        if tool_name.startswith(prefix) and len(prefix) > best_length:
            best_match = label
            best_length = len(prefix)
    return best_match


def _safe_callback(callback: EventCallback) -> EventCallback:
    """Wrap *callback* so exceptions are logged instead of propagated."""

    def _wrapper(event: StreamEvent) -> None:
        try:
            callback(event)
        except (RuntimeError, OSError, asyncio.QueueFull):
            logger.warning(
                "hook=<%s> | event callback raised an exception", "EventPublisher", exc_info=True
            )
        except Exception as e:
            logger.error(
                "hook=<%s> | event callback raised an unexpected exception: %s: %s",
                "EventPublisher",
                type(e).__name__,
                e,
                exc_info=True,
            )
            raise

    return _wrapper


# ============================================================================
# EventPublisher
# ============================================================================


class EventPublisher(HookProvider):
    """Unified event publisher for single-agent and multi-agent orchestrations."""

    def __init__(
        self,
        callback: EventCallback,
        agent_name: str,
        *,
        tool_labels: dict[str, str] | None = None,
        max_result_len: int = 600,
    ) -> None:
        """Initialize the EventPublisher.

        Converts strands hook events into :class:`StreamEvent` objects and
        delivers them to an external callback.  Emits a COMPLETE event at
        the end of each invocation with usage metrics from ``EventLoopMetrics``.

        For TOKEN and REASONING events use :meth:`as_callback_handler` to
        create a strands-compatible ``callback_handler``.

        Args:
            callback: Called with each :class:`StreamEvent`.
            agent_name: Identifier for the agent or orchestrator.
            tool_labels: Optional mapping of tool names to display labels.
            max_result_len: Maximum character length for tool result text
                in TOOL_END events. Default: 600.

        Example::

            publisher = EventPublisher(callback=on_event, agent_name="analyzer")
            agent = Agent(
                hooks=[publisher],
                callback_handler=publisher.as_callback_handler(),
            )
        """
        self._callback = _safe_callback(callback)
        self._agent_name = agent_name
        self._tool_labels = tool_labels or {}
        self._max_result_len = max_result_len
        self._errored = False

    @override
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register hook callbacks for agent and multiagent events."""
        # Agent-level
        registry.add_callback(BeforeInvocationEvent, self._on_agent_start)
        registry.add_callback(AfterModelCallEvent, self._on_model_error)
        registry.add_callback(BeforeToolCallEvent, self._on_tool_start)
        registry.add_callback(AfterToolCallEvent, self._on_tool_end)
        registry.add_callback(AfterInvocationEvent, self._on_complete)
        # Multiagent-level
        registry.add_callback(BeforeNodeCallEvent, self._on_node_start)
        registry.add_callback(AfterNodeCallEvent, self._on_node_stop)
        registry.add_callback(BeforeMultiAgentInvocationEvent, self._on_multiagent_start)
        registry.add_callback(AfterMultiAgentInvocationEvent, self._on_multiagent_complete)

    # -- Agent hooks ---------------------------------------------------------

    def _on_agent_start(self, event: BeforeInvocationEvent) -> None:
        """Emit AGENT_START at the beginning of each agent invocation."""
        self._errored = False
        self._callback(
            StreamEvent(
                type=EventType.AGENT_START,
                agent_name=self._agent_name,
                data={"type": "agent"},
            ),
        )

    def _on_tool_start(self, event: BeforeToolCallEvent) -> None:
        """Register a pending tool call and emit a TOOL_START streaming event."""
        raw_name = event.tool_use.get("name", "unknown")
        tool_label = _resolve_tool_label(raw_name, self._tool_labels) or raw_name
        tool_use_id = event.tool_use.get("toolUseId", "")

        self._callback(
            StreamEvent(
                type=EventType.TOOL_START,
                agent_name=self._agent_name,
                data={
                    "tool_name": raw_name,
                    "tool_label": tool_label,
                    "tool_use_id": tool_use_id,
                    "tool_input": event.tool_use.get("input", {}),
                },
            ),
        )

    def _on_tool_end(self, event: AfterToolCallEvent) -> None:
        """Complete a pending tool call, accumulate the step, and emit TOOL_END."""
        raw_name = event.tool_use.get("name", "unknown")
        tool_label = _resolve_tool_label(raw_name, self._tool_labels) or raw_name
        tool_use_id = event.tool_use.get("toolUseId", "")

        status = "error" if event.exception else "success"

        self._callback(
            StreamEvent(
                type=EventType.TOOL_END,
                agent_name=self._agent_name,
                data={
                    "tool_name": raw_name,
                    "tool_label": tool_label,
                    "tool_use_id": tool_use_id,
                    "status": status,
                    "error": str(event.exception) if event.exception else None,
                    "tool_result": _extract_result_text(event.result, self._max_result_len),
                },
            ),
        )

    def _on_complete(self, event: AfterInvocationEvent) -> None:
        """Emit COMPLETE with usage metrics from EventLoopMetrics.

        Suppressed when the invocation errored — an ERROR event was
        already emitted via :meth:`_on_model_error`.
        """
        if self._errored:
            return

        metrics = event.agent.event_loop_metrics

        # Usage from the latest invocation (current turn only).
        invocation = metrics.latest_agent_invocation
        usage = invocation.usage if invocation else metrics.accumulated_usage

        self._callback(
            StreamEvent(
                type=EventType.COMPLETE,
                agent_name=self._agent_name,
                data={
                    "type": "agent",
                    "usage": {
                        "input_tokens": usage.get("inputTokens", 0),
                        "output_tokens": usage.get("outputTokens", 0),
                        "total_tokens": usage.get("totalTokens", 0),
                    },
                },
            ),
        )

    # -- Model error hook ----------------------------------------------------

    def _on_model_error(self, event: AfterModelCallEvent) -> None:
        """Emit ERROR when a model call fails.

        Fires for provider-level exceptions such as expired credentials,
        throttling, network errors, or any other model API failure.
        Sets ``_errored`` to suppress the subsequent misleading COMPLETE.
        """
        if event.exception is None:
            return

        self._errored = True
        exc = event.exception
        self._callback(
            StreamEvent(
                type=EventType.ERROR,
                agent_name=self._agent_name,
                data={
                    "message": f"{type(exc).__name__}: {exc}",
                    "exception_type": type(exc).__name__,
                },
            ),
        )

    # -- Multiagent hooks ----------------------------------------------------

    def _on_multiagent_start(self, event: BeforeMultiAgentInvocationEvent) -> None:
        """Emit MULTIAGENT_START at the beginning of each multi-agent orchestration."""
        self._callback(
            StreamEvent(
                type=EventType.MULTIAGENT_START,
                agent_name=self._agent_name,
                data={
                    "multiagent_type": event.source.__class__.__name__.lower(),
                },
            ),
        )

    def _on_node_start(self, event: BeforeNodeCallEvent) -> None:
        """Emit NODE_START when a multi-agent orchestration begins a node."""
        self._callback(
            StreamEvent(
                type=EventType.NODE_START,
                agent_name=self._agent_name,
                data={
                    "node_id": event.node_id,
                    "multiagent_type": event.source.__class__.__name__.lower(),
                },
            ),
        )

    def _on_node_stop(self, event: AfterNodeCallEvent) -> None:
        """Emit NODE_STOP when a multi-agent orchestration finishes a node."""
        self._callback(
            StreamEvent(
                type=EventType.NODE_STOP,
                agent_name=self._agent_name,
                data={
                    "node_id": event.node_id,
                    "multiagent_type": event.source.__class__.__name__.lower(),
                },
            ),
        )

    def _on_multiagent_complete(self, event: AfterMultiAgentInvocationEvent) -> None:
        """Emit MULTIAGENT_COMPLETE when the orchestration finishes."""
        self._callback(
            StreamEvent(
                type=EventType.MULTIAGENT_COMPLETE,
                agent_name=self._agent_name,
                data={
                    "multiagent_type": event.source.__class__.__name__.lower(),
                },
            ),
        )

    # -- Callback handler for streaming chunks -------------------------------

    def as_callback_handler(self) -> Callable[..., None]:
        """Return a strands-compatible callback_handler for TOKEN, REASONING, and HANDOFF events.

        Handles the following kwarg patterns emitted by strands:
        - ``data`` (str): A streamed text chunk -> TOKEN event.
        - ``reasoningText`` (str): A reasoning chunk -> REASONING event.
        - ``type == "multiagent_handoff"``: A :class:`~strands.types._events.MultiAgentHandoffEvent`
          fired during Swarm/Graph node transitions -> HANDOFF event.

        Returns:
            A callable compatible with strands ``callback_handler`` interface.
        """

        def _handler(**kwargs: Any) -> None:
            text: str = kwargs.get("data", "")
            if text:
                self._callback(
                    StreamEvent(
                        type=EventType.TOKEN, agent_name=self._agent_name, data={"text": text}
                    ),
                )

            reasoning: str = kwargs.get("reasoningText", "")
            if reasoning:
                self._callback(
                    StreamEvent(
                        type=EventType.REASONING,
                        agent_name=self._agent_name,
                        data={"text": reasoning},
                    ),
                )

            if kwargs.get("type") == "multiagent_handoff":
                self._callback(
                    StreamEvent(
                        type=EventType.HANDOFF,
                        agent_name=self._agent_name,
                        data={
                            "from_node_ids": kwargs.get("from_node_ids", []),
                            "to_node_ids": kwargs.get("to_node_ids", []),
                            "message": kwargs.get("message"),
                        },
                    )
                )

        return _handler
