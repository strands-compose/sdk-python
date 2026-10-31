"""Wrap a ``MultiAgentBase`` as a delegate tool — strands has no ``as_tool`` for one.

An ``Agent`` needs nothing here; :meth:`strands.Agent.as_tool` covers it.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from strands.multiagent import Status
from strands.tools.decorator import DecoratedFunctionTool, tool
from strands.types.tools import ToolContext

from .extractors import extract_block_text, extract_last_message, extract_text

if TYPE_CHECKING:
    from strands.multiagent.base import MultiAgentBase
    from strands.types.content import Message

logger = logging.getLogger(__name__)


def _message_to_tool_result(message: Message) -> dict[str, Any]:
    """Map a ``Message`` to a ``ToolResult``, bypassing the decorator's stringification."""
    content = [
        {"text": text}
        for block in message.get("content", [])
        if isinstance(block, dict) and (text := extract_block_text(block))
    ]
    return {"status": "success", "content": content or [{"text": ""}]}


def multiagent_as_tool(
    node: MultiAgentBase,
    *,
    name: str | None = None,
    description: str,
) -> DecoratedFunctionTool:
    """Wrap a Swarm or Graph as a tool so an agent can delegate to it.

    The orchestration joins the calling agent's request, so its token usage
    counts toward the request's total and limits.

    The caller receives a tool error when:

    - an interrupt is raised inside the orchestration (it cannot be resumed
      across this boundary),
    - the orchestration ends in any status other than ``COMPLETED``, for
      example ``FAILED`` because a node's provider is down or a handoff limit
      is hit,
    - the same wrapped tool is already running (a Swarm or Graph keeps one
      state per object, so concurrent calls would corrupt each other).

    Args:
        node: The orchestration to wrap.
        name: Tool name (defaults to the orchestration's id).
        description: Tool description for the calling LLM.

    Returns:
        A ``DecoratedFunctionTool`` wrapping the orchestration.
    """
    tool_name = name if name is not None else getattr(node, "id", "sub_orchestration")

    lock = threading.Lock()

    @tool(name=tool_name, description=description, context=True)
    async def delegate(input: str, tool_context: ToolContext) -> dict[str, Any]:
        if not lock.acquire(blocking=False):
            return {
                "status": "error",
                "content": [{"text": f"Delegate '{tool_name}' is already processing a request."}],
            }
        try:
            result = await node.invoke_async(
                input, invocation_context=tool_context.invocation_context
            )
        finally:
            lock.release()

        # Returning the result as-is would reach the caller as an empty success,
        # making a pending approval look granted.
        if interrupts := getattr(result, "interrupts", None):
            names = ", ".join(str(getattr(item, "name", item)) for item in interrupts)
            logger.warning(
                "tool=<%s>, interrupts=<%s> | delegate orchestration interrupted, cannot resume",
                tool_name,
                names,
            )
            return {
                "status": "error",
                "content": [
                    {
                        "text": (
                            f"Delegate '{tool_name}' was interrupted ({names}) and cannot be "
                            f"resumed across this delegation boundary."
                        )
                    }
                ],
            }

        if result.status is not Status.COMPLETED:
            detail = extract_text(extract_last_message(result))
            logger.warning(
                "tool=<%s>, status=<%s> | delegate orchestration did not complete",
                tool_name,
                result.status.value,
            )
            return {
                "status": "error",
                "content": [{"text": f"Delegate '{tool_name}' did not finish: {detail}"}],
            }

        return _message_to_tool_result(extract_last_message(result))

    return delegate
