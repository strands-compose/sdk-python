"""Wrap a ``MultiAgentBase`` as a delegate tool — strands has no ``as_tool`` for one.

An ``Agent`` needs nothing here; :meth:`strands.Agent.as_tool` covers it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from strands.tools.decorator import DecoratedFunctionTool, tool

from .extractors import extract_block_text, extract_last_message

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

    An interrupt raised inside the orchestration cannot be resumed across this
    boundary and is reported to the caller as a tool error.

    Args:
        node: The orchestration to wrap.
        name: Tool name (defaults to the orchestration's id).
        description: Tool description for the calling LLM.

    Returns:
        A ``DecoratedFunctionTool`` wrapping the orchestration.
    """
    tool_name = name if name is not None else getattr(node, "id", "sub_orchestration")

    @tool(name=tool_name, description=description)
    async def delegate(input: str) -> dict[str, Any]:
        result = await node.invoke_async(input)

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

        return _message_to_tool_result(extract_last_message(result))

    return delegate
