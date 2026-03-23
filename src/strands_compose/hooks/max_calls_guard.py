"""Max tool-calls guard hook.

Prevents infinite tool-call loops by counting tool invocations per agent
call and stopping the agent when a threshold is reached.  Uses strands'
``invocation_state`` dict, which is created fresh for each ``agent()`` call,
so the counter resets automatically between invocations.

Two-phase shutdown:

1. **First violation** — cancel the tool call and tell the LLM to stop using
   tools and write a final answer.  The event loop continues so the LLM gets
   one more turn to produce a closing response.
2. **Subsequent violations** — the LLM ignored the warning and tried to call
   another tool.  Hard-stop the event loop immediately.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import BeforeToolCallEvent

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

logger = logging.getLogger(__name__)


class MaxToolCallsGuard(HookProvider):
    """Stops the agent after a maximum number of tool calls per invocation."""

    _COUNT_KEY = "max_tool_calls_guard_count"
    _LIMIT_HIT_KEY = "max_tool_calls_guard_limit_hit"

    def __init__(self, max_calls: int = 25) -> None:
        """Initialize the MaxToolCallsGuard.

        On first violation the LLM is instructed to stop using tools and write a
        final answer (graceful shutdown).  If the LLM ignores that and requests
        another tool call, the event loop is terminated immediately (hard stop).

        Uses strands' ``invocation_state`` dict for per-invocation state — the
        counter and flags reset automatically on each new ``agent()`` call.

        Args:
            max_calls: Maximum tool calls allowed per invocation. Default: 25.
        """
        self.max_calls = max_calls

    @override
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register the BeforeToolCallEvent callback."""
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool)

    def _on_before_tool(self, event: BeforeToolCallEvent) -> None:
        """Increment call counter; cancel and warn or hard-stop if limit exceeded."""
        count = event.invocation_state.get(self._COUNT_KEY, 0) + 1
        event.invocation_state[self._COUNT_KEY] = count

        if count <= self.max_calls:
            return

        if not event.invocation_state.get(self._LIMIT_HIT_KEY, False):
            # First violation — graceful: cancel the tool, let the LLM respond.
            logger.warning(
                "count=<%d>, limit=<%d> | tool call limit reached, giving LLM one final turn",
                count - 1,
                self.max_calls,
            )
            event.cancel_tool = (
                f"You have reached your tool call limit for this response ({self.max_calls} calls). "
                "Do not call any more tools in this response — write your final answer now. "
                "The limit resets on the next message and you may use tools freely again."
            )
            event.invocation_state[self._LIMIT_HIT_KEY] = True
        else:
            # LLM ignored the warning — hard stop.
            logger.warning(
                "limit=<%d> | agent ignored tool call limit, stopping event loop",
                self.max_calls,
            )
            event.cancel_tool = (
                f"Tool call limit ({self.max_calls}) exceeded. Agent loop terminated."
            )
            event.invocation_state.setdefault("request_state", {})["stop_event_loop"] = True
