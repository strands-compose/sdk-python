"""Message extraction and serialization utilities for agent and multi-agent results."""

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


def extract_text(message: Message | None) -> str:
    """Return the last text block from a message, or an empty string."""
    if not message:
        return ""
    for block in reversed(message.get("content", [])):
        if isinstance(block, dict) and "text" in block:
            return block["text"]
    return ""


def extract_last_message(result: Any) -> Message:
    """Extract the final message from an agent, orchestration, or node result.

    Args:
        result: An ``AgentResult``, ``MultiAgentResult``, ``NodeResult``,
            or any object.

    Returns:
        The extracted ``Message``.
    """
    if isinstance(result, AgentResult):
        return result.message

    if isinstance(result, MultiAgentResult):
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


def serialize_multiagent_result(result: MultiAgentResult) -> dict[str, Any]:
    """Serialize a ``MultiAgentResult`` with execution metadata omitted by ``to_dict()``.

    Extends ``result.to_dict()`` with fields only available on the live object:

    - ``last_node_id`` — id of the truly last executing node, derived from
      ``node_history`` / ``execution_order`` (not dict insertion order).
    - ``response`` — plain-text answer from that node, ready to use
      directly without any further extraction.
    - ``swarm.node_history`` — full ordered execution trace including repeated
      visits (``SwarmResult`` only).
    - ``graph.execution_order``, ``graph.edges``, ``graph.entry_points``, and
      node counts (``GraphResult`` only).

    Args:
        result: A live ``MultiAgentResult``, ``SwarmResult``, or ``GraphResult``
            returned directly by ``invoke_async``.

    Returns:
        A JSON-serializable dict extending ``result.to_dict()``.
    """
    data = result.to_dict()

    last_node_id = resolve_last_node_id(result)
    data["last_node_id"] = last_node_id

    final_message = extract_last_message(result)
    data["response"] = extract_text(final_message)

    # SwarmResult extras — node_history is a list[SwarmNode]
    node_history: list[Any] | None = getattr(result, "node_history", None)
    if node_history is not None:
        data["swarm"] = {
            "node_history": [str(n.node_id) for n in node_history],
        }

    # GraphResult extras — execution_order, edges, node counts
    execution_order: list[Any] | None = getattr(result, "execution_order", None)
    if execution_order is not None:
        edges_raw: list[Any] = getattr(result, "edges", []) or []
        entry_points_raw: list[Any] = getattr(result, "entry_points", []) or []

        edges: list[list[str]] = []
        for edge in edges_raw:
            if isinstance(edge, tuple) and len(edge) == 2:
                edges.append([str(edge[0].node_id), str(edge[1].node_id)])
            else:
                # GraphEdge dataclass with from_node / to_node attributes
                from_id = str(getattr(getattr(edge, "from_node", None), "node_id", edge))
                to_id = str(getattr(getattr(edge, "to_node", None), "node_id", edge))
                edges.append([from_id, to_id])

        data["graph"] = {
            "execution_order": [str(n.node_id) for n in execution_order],
            "edges": edges,
            "entry_points": [str(getattr(ep, "node_id", ep)) for ep in entry_points_raw],
            "completed_nodes": getattr(result, "completed_nodes", 0),
            "failed_nodes": getattr(result, "failed_nodes", 0),
            "interrupted_nodes": getattr(result, "interrupted_nodes", 0),
        }

    return data
