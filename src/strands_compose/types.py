"""Shared types for the core package.

Centralises the ``Node`` union so it is defined exactly once and
imported everywhere else, rather than being duplicated in
``orchestration`` and ``config/resolvers``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from strands import Agent
from strands.multiagent.base import MultiAgentBase

# A node is either a plain Agent or a built multi-agent orchestration
# (Swarm, Graph, or any other MultiAgentBase subclass).
Node = Agent | MultiAgentBase


class EventType(StrEnum):
    """Event type constants for :class:`StreamEvent`.

    ``StrEnum`` values are plain strings, so ``== "token"`` comparisons
    work unchanged.
    """

    # Single-agent events
    AGENT_START = "agent_start"
    TOKEN = "token"  # nosec B105 — event type constant, not a credential
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    REASONING = "reasoning"
    COMPLETE = "complete"
    ERROR = "error"

    # Multi-agent events
    NODE_START = "node_start"
    NODE_STOP = "node_stop"
    HANDOFF = "handoff"
    MULTIAGENT_START = "multiagent_start"
    MULTIAGENT_COMPLETE = "multiagent_complete"


@dataclass
class StreamEvent:
    """A typed event from agent or multi-agent execution.

    Produced by :class:`~strands_compose.hooks.EventPublisher` for
    all agent activity: ``TOKEN``, ``REASONING``, ``TOOL_START``, ``TOOL_END``,
    ``COMPLETE``, ``ERROR``, ``NODE_START``, ``NODE_STOP``,
    ``HANDOFF``, ``MULTIAGENT_COMPLETE``.

    Attributes:
        type: Event type identifier (one of the :class:`EventType` values).
        agent_name: Name of the agent that produced this event.
        timestamp: When the event occurred.
        data: Event-specific payload.
    """

    type: str
    agent_name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    data: dict[str, Any] = field(default_factory=dict)

    def asdict(self) -> dict[str, Any]:
        """Convert this StreamEvent to a flat dict for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamEvent:
        """Deserialize a dict into a StreamEvent.

        Restores all fields produced by :meth:`asdict`, including the
        ``timestamp`` (parsed from its ISO-8601 string representation).

        Args:
            data: A dict as produced by :meth:`asdict`.

        Returns:
            A new StreamEvent instance.
        """
        ts_raw = data.get("timestamp")
        if isinstance(ts_raw, str):
            ts = datetime.fromisoformat(ts_raw)
        elif isinstance(ts_raw, datetime):
            ts = ts_raw
        else:
            ts = datetime.now(tz=timezone.utc)

        return cls(
            type=data.get("type", ""),
            agent_name=data.get("agent_name", ""),
            timestamp=ts,
            data=data.get("data", {}),
        )

    def __eq__(self, other: object) -> bool:
        """Compare events by type, agent_name, and data (ignoring timestamp)."""
        if not isinstance(other, StreamEvent):
            return NotImplemented
        return (self.type, self.agent_name, self.data) == (other.type, other.agent_name, other.data)

    def __hash__(self) -> int:
        """Hash based on type and agent_name (data is unhashable)."""
        return hash((self.type, self.agent_name))
