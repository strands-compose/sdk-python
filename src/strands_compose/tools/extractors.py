"""Message extraction utilities for agent and multi-agent results.

Key Features:
    - Extract the last message from strands Agent and MultiAgent results
    - Extract text from messages when a string-only fallback is needed
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


def _message_from_text(text: str) -> Message:
    """Build an assistant message from text."""
    return {"role": "assistant", "content": [{"text": text}]}


def _extract_last_message_from_multi_agent_result(result: MultiAgentResult) -> Message:
    """Extract the final message from a ``MultiAgentResult``."""
    last_node_id = resolve_last_node_id(result)

    if last_node_id and last_node_id in result.results:
        message = extract_last_message(result.results[last_node_id])
        if message is not None:
            return message

    for node_result in reversed(list(result.results.values())):
        message = extract_last_message(node_result)
        if message is not None:
            return message

    logger.warning("status=<%s> | no message extracted from MultiAgentResult", result.status)
    return _message_from_text(
        f"[orchestration completed with status {result.status.value} but produced no message output]"
    )


def extract_text_from_message(message: Message | None) -> str | None:
    """Extract the last text block from a message.

    Strands ``ContentBlock`` uses ``{"text": "..."}`` for text blocks (no
    ``"type"`` wrapper). This helper scans content blocks in reverse and
    returns the last text block. Use it only when a caller explicitly needs
    plain text; ``extract_last_message`` preserves the complete message.

    Args:
        message: A strands ``Message`` dict (e.g. ``AgentResult.message``).

    Returns:
        The last text string, or ``None`` if no text blocks exist.
    """
    if not message:
        return None
    content = message.get("content", [])
    for block in reversed(content):
        if isinstance(block, dict) and "text" in block:
            return block["text"]
    return None


def extract_last_message(result: Any) -> Message:
    """Extract the final message from an agent, orchestration, or node result.

    Dispatches to the appropriate extractor based on the result type:
    - ``AgentResult`` returns ``result.message`` directly.
    - ``MultiAgentResult`` drills into the last executing node's message.
    - ``NodeResult`` unwraps the inner payload and dispatches recursively.
    - Unknown types fall back to an assistant text message containing
      ``str(result)``.

    Args:
        result: An ``AgentResult``, ``MultiAgentResult``, ``NodeResult``,
            or any object.

    Returns:
        The extracted ``Message``. This can be wrapped in a one-item list and
        passed to ``Agent.invoke_async`` as ``Messages`` when richer content
        such as images or documents must be preserved.
    """
    if isinstance(result, AgentResult):
        return result.message

    if isinstance(result, MultiAgentResult):
        return _extract_last_message_from_multi_agent_result(result)

    if isinstance(result, NodeResult):
        inner = result.result
        if isinstance(inner, (AgentResult, MultiAgentResult)):
            return extract_last_message(inner)
        logger.warning("error=<%s> | nested node produced an exception", inner)
        return _message_from_text(f"[nested agent error: {inner}]")

    logger.warning(
        "type=<%s> | unexpected result type in extract_last_message", type(result).__name__
    )
    return _message_from_text(str(result))


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
