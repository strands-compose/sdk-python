"""Node wrapping utilities for delegation.

Provides ``node_as_tool`` and ``node_as_async_tool`` for wrapping
``Agent`` / ``MultiAgentBase`` nodes as ``AgentTool`` instances.

Key Features:
    - Sync and async tool wrappers for Agent and MultiAgentBase nodes
    - Automatic tool name resolution from agent_id or node id
    - Text extraction from both single-agent and multi-agent results
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from strands import Agent
from strands.tools.decorator import DecoratedFunctionTool, tool

from .extractors import extract_last_text_block

if TYPE_CHECKING:
    from ..types import Node


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


def node_as_tool(
    node: Node,
    *,
    name: str | None = None,
    description: str,
) -> DecoratedFunctionTool:
    """Wrap an Agent or MultiAgentBase as an ``AgentTool`` for delegation.

    For Agent nodes, invokes the agent and extracts text from the response.
    For MultiAgentBase nodes (Swarm, Graph), invokes and stringifies the result.

    Args:
        node: Agent or MultiAgentBase instance.
        name: Tool name (defaults to node id).
        description: Tool description for the parent LLM.

    Returns:
        An ``AgentTool`` (``DecoratedFunctionTool``) wrapping the node.
    """
    tool_name = _resolve_tool_name(node, name)

    @tool(name=tool_name, description=description)
    def delegate(input: str) -> str:
        result = node(input)
        return extract_last_text_block(result)

    return delegate


def node_as_async_tool(
    node: Node,
    *,
    name: str | None = None,
    description: str,
) -> DecoratedFunctionTool:
    """Wrap an Agent or MultiAgentBase as an async ``AgentTool`` for delegation.

    For Agent nodes, uses ``invoke_async`` for live event streaming.
    For MultiAgentBase nodes, awaits ``invoke_async``.

    Args:
        node: Agent or MultiAgentBase instance.
        name: Tool name.
        description: Tool description for the parent LLM.

    Returns:
        An ``AgentTool`` (``DecoratedFunctionTool``) wrapping the node.
    """
    tool_name = _resolve_tool_name(node, name)

    @tool(name=tool_name, description=description)
    async def delegate(input: str) -> str:
        result = await node.invoke_async(input)
        return extract_last_text_block(result)

    return delegate
