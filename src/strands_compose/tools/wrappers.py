"""Node wrapping utilities for delegation.

Provides ``node_as_tool`` and ``node_as_async_tool`` for wrapping
``Agent`` / ``MultiAgentBase`` nodes as ``AgentTool`` instances.

Key Features:
    - Sync and async tool wrappers for Agent and MultiAgentBase nodes
    - Automatic tool name resolution from agent_id or node id
    - Message content preservation from single-agent and multi-agent results
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from strands import Agent
from strands.tools.decorator import DecoratedFunctionTool, tool
from strands.types.content import Message

from .extractors import extract_last_message, extract_text

if TYPE_CHECKING:
    from ..types import Node


# ToolResultContent only accepts these 4 keys (subset of ContentBlock's 10).
# Passing model-only keys (toolUse, reasoningContent, …) would produce malformed content.
_TOOL_RESULT_CONTENT_KEYS = ("document", "image", "json", "text")


def _resolve_tool_name(node: Node, name: str | None) -> str:
    """Resolve the tool name for a node.

    For ``Agent`` nodes, defaults to ``agent.agent_id``.
    For ``MultiAgentBase`` nodes, defaults to ``node.id`` or ``"sub_orchestration"``.

    Args:
        node: Agent or MultiAgentBase instance.
        name: Explicit tool name override, or ``None`` to use the default.

    Returns:
        The resolved tool name string.
    """
    if name is not None:
        return name
    if isinstance(node, Agent):
        return node.agent_id
    return getattr(node, "id", "sub_orchestration")


def _message_to_tool_result(message: Message) -> dict[str, Any]:
    """Map a ``Message`` to a ``ToolResult`` dict (``strands.types.tools.ToolResult``).

    Returning a pre-shaped ``{"status": ..., "content": [...]}`` dict bypasses
    ``DecoratedFunctionTool._wrap_tool_result``'s plain-text auto-wrapping, so
    non-text blocks (``image``, ``document``, ``json``) are preserved across
    the delegation boundary. Only ``ToolResultContent`` keys are kept — model-
    only blocks such as ``toolUse`` and ``reasoningContent`` are dropped.

    Args:
        message: The final ``Message`` returned by a sub-agent or orchestration.

    Returns:
        A ``ToolResult``-shaped dict ready for the Strands decorator to pass through.
    """
    content: list[dict[str, Any]] = []
    for block in message.get("content", []):
        source_block = cast(dict[str, Any], block)
        tool_result_block = {
            key: source_block[key] for key in _TOOL_RESULT_CONTENT_KEYS if key in source_block
        }
        if tool_result_block:
            content.append(tool_result_block)

    if content:
        return {"status": "success", "content": content}

    return {"status": "success", "content": [{"text": extract_text(message) or ""}]}


def node_as_tool(
    node: Node,
    *,
    name: str | None = None,
    description: str,
) -> DecoratedFunctionTool:
    """Wrap an Agent or MultiAgentBase as an ``AgentTool`` for delegation.

    For Agent nodes, invokes the agent and returns the final message content
    as a Strands tool result. For MultiAgentBase nodes (Swarm, Graph),
    resolves the last executed node and returns its final message content.

    Args:
        node: Agent or MultiAgentBase instance.
        name: Tool name (defaults to node id).
        description: Tool description for the parent LLM.

    Returns:
        An ``AgentTool`` (``DecoratedFunctionTool``) wrapping the node.
    """
    tool_name = _resolve_tool_name(node, name)

    @tool(name=tool_name, description=description)
    def delegate(input: str) -> dict[str, Any]:
        result = node(input)
        return _message_to_tool_result(extract_last_message(result))

    return delegate


def node_as_async_tool(
    node: Node,
    *,
    name: str | None = None,
    description: str,
) -> DecoratedFunctionTool:
    """Wrap an Agent or MultiAgentBase as an async ``AgentTool`` for delegation.

    For Agent nodes, uses ``invoke_async`` for live event streaming. For
    MultiAgentBase nodes, awaits ``invoke_async``. In both cases the final
    message content is returned as a Strands tool result so non-text blocks
    such as images and documents are preserved when possible.

    Args:
        node: Agent or MultiAgentBase instance.
        name: Tool name.
        description: Tool description for the parent LLM.

    Returns:
        An ``AgentTool`` (``DecoratedFunctionTool``) wrapping the node.
    """
    tool_name = _resolve_tool_name(node, name)

    @tool(name=tool_name, description=description)
    async def delegate(input: str) -> dict[str, Any]:
        result = await node.invoke_async(input)
        return _message_to_tool_result(extract_last_message(result))

    return delegate
