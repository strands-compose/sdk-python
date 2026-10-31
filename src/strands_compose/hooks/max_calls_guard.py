"""Max tool-calls guard hook.

Prevents infinite tool-call loops by counting tool invocations per agent
call and stopping the agent when a threshold is reached.  Counters live in
strands' ``invocation_state`` dict, keyed per agent because a Swarm or Graph
shares one dict across all of its nodes, and reset at the start of every
invocation.

Two-phase shutdown:

1. **First violation** — cancel the tool call and tell the LLM to stop using
   tools and write a final answer.  The event loop continues so the LLM gets
   one more turn to produce a closing response.
2. **Subsequent violations** — the LLM ignored the warning and tried to call
   another tool.  End the invocation with ``stop_reason="cancelled"``.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import BeforeInvocationEvent, BeforeToolCallEvent

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
        another tool call, the invocation ends with ``stop_reason="cancelled"``
        (hard stop).  The stop is deferred: tools already requested in the
        current turn finish, then the loop exits before the next model call.

        State is kept per agent in strands' ``invocation_state`` dict and reset
        at the start of every invocation, so a node revisited in a Graph or
        Swarm counts from zero.

        Args:
            max_calls: Maximum tool calls allowed per invocation. Default: 25.
        """
        self.max_calls = max_calls

    @override
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register the invocation reset and BeforeToolCallEvent callbacks."""
        registry.add_callback(BeforeInvocationEvent, self._on_before_invocation)
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool)

    @staticmethod
    def _key(agent: Any, name: str) -> str:
        """Return the ``invocation_state`` key for ``name`` scoped to ``agent``.

        ``id(agent)`` rather than ``agent_id``: hand-built agents all default to the same id.
        """
        return f"{name}:{id(agent)}"

    def _on_before_invocation(self, event: BeforeInvocationEvent) -> None:
        """Reset this agent's counter and flag at the start of an invocation."""
        for name in (self._COUNT_KEY, self._LIMIT_HIT_KEY):
            event.invocation_state.pop(self._key(event.agent, name), None)

    def _on_before_tool(self, event: BeforeToolCallEvent) -> None:
        """Increment call counter; cancel and warn or hard-stop if limit exceeded."""
        count_key = self._key(event.agent, self._COUNT_KEY)
        limit_hit_key = self._key(event.agent, self._LIMIT_HIT_KEY)

        count = event.invocation_state.get(count_key, 0) + 1
        event.invocation_state[count_key] = count

        if count <= self.max_calls:
            return

        if not event.invocation_state.get(limit_hit_key, False):
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
            event.invocation_state[limit_hit_key] = True
        else:
            # LLM ignored the warning — hard stop.
            logger.warning(
                "limit=<%d> | agent ignored tool call limit, ending invocation",
                self.max_calls,
            )
            message = f"Tool call limit ({self.max_calls}) exceeded. Agent loop terminated."
            event.cancel_tool = message
            event.agent.cancel(message=message, after_current_tools=True)
