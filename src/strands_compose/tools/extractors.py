"""Text extraction utilities for agent and multi-agent results.

Key Features:
    - Extract the last text block from strands Agent and MultiAgent results
    - Support for SwarmResult and GraphResult node resolution
    - Recursive extraction through nested orchestration results
"""

from __future__ import annotations

import logging
from typing import Any

from strands.agent.agent_result import AgentResult
from strands.multiagent.base import MultiAgentResult, NodeResult
from strands.types.content import Message

logger = logging.getLogger(__name__)


def extract_text_from_message(message: Message | None) -> str | None:
    """Extract the last text block from a message dict.

    Strands ``ContentBlock`` uses ``{"text": "..."}`` for text blocks (no
    ``"type"`` wrapper).  This helper collects all content blocks that
    contain a ``"text"`` key and returns the last one — the model's final
    turn can interleave text and tool-use blocks, and only the last text
    block carries the actual answer we want to bubble up.

    Args:
        message: A strands ``Message`` dict (e.g. ``AgentResult.message``).

    Returns:
        The last text string, or ``None`` if no text blocks exist.
    """
    if not message:
        return None
    content = message.get("content", [])
    text_blocks = [
        block["text"] for block in content if isinstance(block, dict) and "text" in block
    ]
    if text_blocks:
        return text_blocks[-1]
    return None


def extract_text_from_agent_result(result: AgentResult) -> str:
    """Extract the final text answer from an ``AgentResult``.

    Tries the last text block in ``result.message``.  Falls back to
    ``str(result)`` which handles structured output and interrupts.

    Args:
        result: An ``AgentResult`` from a single agent invocation.

    Returns:
        The extracted answer text.
    """
    text = extract_text_from_message(result.message)
    if text is not None:
        return text
    return str(result)


def extract_text_from_multi_agent_result(result: MultiAgentResult) -> str:
    """Extract the final answer text from a ``MultiAgentResult``.

    ``MultiAgentResult`` (and subclasses ``SwarmResult``, ``GraphResult``)
    store per-node results in ``result.results``.  This helper locates the
    *last* agent that ran — using ``node_history`` for swarms and
    ``execution_order`` for graphs — and extracts its text.  Falls back to
    iterating all node results in reverse order.

    Args:
        result: A ``MultiAgentResult`` (or ``SwarmResult`` / ``GraphResult``).

    Returns:
        The extracted answer text, or a descriptive fallback string.
    """
    # Determine the last agent that executed
    last_node_id = resolve_last_node_id(result)

    if last_node_id and last_node_id in result.results:
        text = extract_text_from_node_result(result.results[last_node_id])
        if text is not None:
            return text

    # Fallback: scan all node results in reverse
    for node_result in reversed(list(result.results.values())):
        text = extract_text_from_node_result(node_result)
        if text is not None:
            return text

    logger.warning("status=<%s> | no text extracted from MultiAgentResult", result.status)
    return (
        f"[orchestration completed with status {result.status.value} but produced no text output]"
    )


def resolve_last_node_id(result: MultiAgentResult) -> str | None:
    """Determine the id of the last node that executed in a multi-agent result.

    Args:
        result: A ``MultiAgentResult`` (or subclass).

    Returns:
        The node id string, or ``None`` if it cannot be determined.
    """
    # SwarmResult.node_history — list[SwarmNode], each has .node_id
    node_history: list[Any] | None = getattr(result, "node_history", None)
    if node_history:
        return str(node_history[-1].node_id)

    # GraphResult.execution_order — list[GraphNode], each has .node_id
    execution_order: list[Any] | None = getattr(result, "execution_order", None)
    if execution_order:
        return str(execution_order[-1].node_id)

    return None


def extract_text_from_node_result(node_result: NodeResult) -> str | None:
    """Extract text from a single ``NodeResult``.

    Handles all three payload shapes:
    - ``AgentResult`` — extracts text from ``.message``.
    - Nested ``MultiAgentResult`` — recurses into it.
    - ``Exception`` — returns the error message.

    Args:
        node_result: A ``NodeResult`` from a multi-agent execution.

    Returns:
        Extracted text, or ``None`` if no usable text is found.
    """
    inner = node_result.result

    if isinstance(inner, AgentResult):
        text = extract_text_from_message(inner.message)
        if text is not None:
            return text
        fallback = str(inner)
        if fallback.strip():
            return fallback
        return None

    if isinstance(inner, MultiAgentResult):
        return extract_text_from_multi_agent_result(inner)

    if isinstance(inner, Exception):
        logger.warning("error=<%s> | nested node produced an exception", inner)
        return f"[nested agent error: {inner}]"

    return None


def extract_last_text_block(result: Any) -> str:
    """Extract the final text answer from an agent or orchestration result.

    Dispatches to the appropriate extractor based on the result type:
    - ``AgentResult`` — extracts the last text block from the message.
    - ``MultiAgentResult`` (``SwarmResult``, ``GraphResult``) — drills into
      the last executing node's ``AgentResult``.
    - Unknown types — falls back to ``str(result)``.

    Args:
        result: An ``AgentResult``, ``MultiAgentResult``, or any object.

    Returns:
        The extracted answer text.
    """
    if isinstance(result, AgentResult):
        return extract_text_from_agent_result(result)

    if isinstance(result, MultiAgentResult):
        return extract_text_from_multi_agent_result(result)

    # Unknown result type — best-effort fallback.
    logger.warning(
        "type=<%s> | unexpected result type in extract_last_text_block", type(result).__name__
    )
    return str(result)
