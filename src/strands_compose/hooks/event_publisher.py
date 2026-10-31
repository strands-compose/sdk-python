"""EventPublisher hook for streaming agent activities to external consumers."""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncGenerator, Callable
from typing import Any

from strands.hooks import HookProvider, HookRegistry
from strands.middleware import InvokeModelContext, MiddlewareNext, TypedEvent
from strands.multiagent.graph import Graph
from strands.multiagent.swarm import Swarm

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
from strands.types.event_loop import Usage

from ..manifest import model_descriptor
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


def _usage_payload(usage: Usage) -> dict[str, int]:
    """Convert strands token usage to the ``usage`` payload of a stream event.

    Values are passed through as strands reports them. Whether ``input_tokens``
    includes the cache counts depends on the provider; see the streaming chapter.

    Args:
        usage: A strands ``Usage`` (camelCase keys, any of which may be absent).

    Returns:
        A dict with ``input_tokens``, ``output_tokens``, ``total_tokens``,
        ``cache_read_input_tokens`` and ``cache_write_input_tokens``, each defaulting to 0.
    """
    return {
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
        "total_tokens": usage.get("totalTokens", 0),
        "cache_read_input_tokens": usage.get("cacheReadInputTokens", 0),
        "cache_write_input_tokens": usage.get("cacheWriteInputTokens", 0),
    }


def _safe_callback(callback: EventCallback) -> EventCallback:
    """Swallow transport failures so a dead consumer cannot kill the agent run.

    Any other exception is re-raised — that means the callback itself is broken.
    """

    def _wrapper(event: StreamEvent) -> None:
        try:
            callback(event)
        except (RuntimeError, OSError, asyncio.QueueFull):
            logger.warning(
                "hook=<%s> | event callback raised an exception", "EventPublisher", exc_info=True
            )
        except Exception:
            logger.exception(
                "hook=<%s> | event callback raised an unexpected exception", "EventPublisher"
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
        max_result_len: int = 600,
    ) -> None:
        """Initialize the EventPublisher.

        Converts strands hook events into :class:`StreamEvent` objects and
        delivers them to an external callback.  Emits an AGENT_COMPLETE event at
        the end of each invocation with usage metrics from ``EventLoopMetrics``.

        TOKEN and REASONING events come from :meth:`observe_model_stream`, a
        model-stream middleware that must be registered separately.

        Args:
            callback: Called with each :class:`StreamEvent`.
            agent_name: Identifier for the agent or orchestrator.
            max_result_len: Maximum character length for tool result text
                in TOOL_END events. Default: 600.

        Example::

            publisher = EventPublisher(callback=on_event, agent_name="analyzer")
            agent = Agent(hooks=[publisher])
            agent.add_middleware(InvokeModelStage, publisher.observe_model_stream)
        """
        self._callback = _safe_callback(callback)
        self._agent_name = agent_name
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
            ),
        )

    def _on_tool_start(self, event: BeforeToolCallEvent) -> None:
        """Register a pending tool call and emit a TOOL_START streaming event."""
        raw_name = event.tool_use.get("name", "unknown")
        tool_use_id = event.tool_use.get("toolUseId", "")

        self._callback(
            StreamEvent(
                type=EventType.TOOL_START,
                agent_name=self._agent_name,
                data={
                    "tool_name": raw_name,
                    "tool_use_id": tool_use_id,
                    "tool_input": event.tool_use.get("input", {}),
                },
            ),
        )

    def _on_tool_end(self, event: AfterToolCallEvent) -> None:
        """Complete a pending tool call, accumulate the step, and emit TOOL_END."""
        raw_name = event.tool_use.get("name", "unknown")
        tool_use_id = event.tool_use.get("toolUseId", "")

        status = "error" if event.exception else "success"

        self._callback(
            StreamEvent(
                type=EventType.TOOL_END,
                agent_name=self._agent_name,
                data={
                    "tool_name": raw_name,
                    "tool_use_id": tool_use_id,
                    "status": status,
                    "error": str(event.exception) if event.exception else None,
                    "tool_result": _extract_result_text(event.result, self._max_result_len),
                },
            ),
        )

    def _on_complete(self, event: AfterInvocationEvent) -> None:
        """Emit AGENT_COMPLETE with usage metrics from EventLoopMetrics.

        Includes ``stop_reason`` and a ``model`` dict with ``model_id`` and ``provider`` (same
        values reported in the session manifest) so consumers can compute
        cost directly from this event without a manifest round-trip.

        Suppressed when the invocation errored — an ERROR event was
        already emitted via :meth:`_on_model_error`.
        """
        if self._errored:
            return

        result = event.result
        if result is not None and result.stop_reason == "interrupt":
            for interrupt in result.interrupts or []:
                self._callback(
                    StreamEvent(
                        type=EventType.INTERRUPT,
                        agent_name=self._agent_name,
                        data={
                            "interrupt_id": interrupt.id,
                            "name": interrupt.name,
                            "reason": interrupt.reason,
                        },
                    ),
                )
            return

        # Usage from the latest invocation (current turn only).
        metrics = event.agent.event_loop_metrics
        invocation = metrics.latest_agent_invocation
        usage = invocation.usage if invocation else metrics.accumulated_usage

        model = model_descriptor(event.agent)

        data: dict[str, Any] = {
            "usage": _usage_payload(usage),
            "stop_reason": result.stop_reason if result is not None else None,
            "model": {
                "model_id": model.model_id,
                "provider": model.provider,
            },
            "text": str(result) if result is not None else "",
            "message": result.message if result is not None else {},
        }

        self._callback(
            StreamEvent(
                type=EventType.AGENT_COMPLETE,
                agent_name=self._agent_name,
                data=data,
            ),
        )

    # -- Model error hook ----------------------------------------------------

    def _on_model_error(self, event: AfterModelCallEvent) -> None:
        """Emit ERROR when a model call fails.

        Fires for provider-level exceptions such as expired credentials,
        throttling, network errors, or any other model API failure.
        Sets ``_errored`` to suppress the subsequent misleading AGENT_COMPLETE.
        """
        if event.exception is None:
            return

        self._errored = True
        self._callback(
            StreamEvent(
                type=EventType.ERROR,
                agent_name=self._agent_name,
                data={
                    "text": f"{event.exception}",
                    "exception_type": type(event.exception).__name__,
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
        """Emit NODE_STOP when a node finishes, then HANDOFF if a Swarm hands off from it.

        NODE_STOP carries ``status``, ``execution_time_ms`` and ``usage`` from the
        node's result. The usage is the node's total, which overlaps the node
        agent's own AGENT_COMPLETE usage; do not sum both.

        strands emits its native handoff event only on the orchestrator's own
        stream, never to hooks or callback handlers. ``AfterNodeCallEvent`` fires
        before strands applies the handoff, so the target is still on ``state``.
        """
        data: dict[str, Any] = {
            "node_id": event.node_id,
            "multiagent_type": event.source.__class__.__name__.lower(),
        }
        source = event.source
        if isinstance(source, (Swarm, Graph)) and (
            node_result := source.state.results.get(event.node_id)
        ):
            data["status"] = node_result.status.value
            data["execution_time_ms"] = node_result.execution_time
            data["usage"] = _usage_payload(node_result.accumulated_usage)
        self._callback(
            StreamEvent(type=EventType.NODE_STOP, agent_name=self._agent_name, data=data)
        )

        if isinstance(source, Swarm) and (target := source.state.handoff_node) is not None:
            self._callback(
                StreamEvent(
                    type=EventType.HANDOFF,
                    agent_name=self._agent_name,
                    data={
                        "from_node_ids": [event.node_id],
                        "to_node_ids": [target.node_id],
                        "message": source.state.handoff_message or "Agent handoff occurred",
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

    # -- Model stream middleware ---------------------------------------------

    async def observe_model_stream(
        self,
        context: InvokeModelContext,
        next_fn: MiddlewareNext[InvokeModelContext, TypedEvent],
    ) -> AsyncGenerator[TypedEvent, None]:
        """``InvokeModelStage`` Wrap handler that emits TOKEN and REASONING events.

        Every streamed event is forwarded unchanged. Text deltas arrive under
        the ``data`` key and reasoning deltas under ``reasoningText``.

        No hook fires per streamed chunk, so TOKEN and REASONING need this
        handler. Register it with
        ``agent.add_middleware(InvokeModelStage, publisher.observe_model_stream)``.
        The first middleware registered is the outermost, so this handler
        sees rewrites by middleware registered after it, not by middleware
        registered before it (for example by a plugin at construction).

        Args:
            context: The model call about to run.
            next_fn: Continues the middleware chain and yields the model's events.

        Yields:
            Each event from ``next_fn``, unchanged.
        """
        async for event in next_fn(context):
            if text := event.get("data"):
                self._callback(
                    StreamEvent(
                        type=EventType.TOKEN, agent_name=self._agent_name, data={"text": text}
                    ),
                )
            if reasoning := event.get("reasoningText"):
                self._callback(
                    StreamEvent(
                        type=EventType.REASONING,
                        agent_name=self._agent_name,
                        data={"text": reasoning},
                    ),
                )
            yield event
