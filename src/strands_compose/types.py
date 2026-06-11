"""Shared types for the core package.

This module is the single canonical home for cross-package types:

- ``Node`` — alias for ``Agent | MultiAgentBase``, the kinds of nodes that
  participate in a session.
- ``EventType`` and ``StreamEvent`` — the typed-event protocol used by the
  event queue and external consumers.
- The ``SessionManifest`` family of Pydantic models — the schema describing a
  wired session at invocation time. The manifest schema is intentionally
  decoupled from the YAML config schema in ``config.schema``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
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
    INTERRUPT = "interrupt"
    AGENT_COMPLETE = "agent_complete"
    ERROR = "error"

    # Multi-agent events
    NODE_START = "node_start"
    NODE_STOP = "node_stop"
    HANDOFF = "handoff"
    MULTIAGENT_START = "multiagent_start"
    MULTIAGENT_COMPLETE = "multiagent_complete"

    # Session-level events
    SESSION_START = "session_start"
    SESSION_END = "session_end"


@dataclass
class StreamEvent:
    """A typed event from agent or multi-agent execution.

    Per-agent activity (``AGENT_START``, ``TOKEN``, ``REASONING``,
    ``TOOL_START``, ``TOOL_END``, ``INTERRUPT``, ``AGENT_COMPLETE``, ``ERROR``,
    ``NODE_START``, ``NODE_STOP``, ``HANDOFF``, ``MULTIAGENT_START``,
    ``MULTIAGENT_COMPLETE``) is produced by
    :class:`~strands_compose.hooks.EventPublisher`. Session-level events
    (``SESSION_START``, ``SESSION_END``) are produced by the queue/wiring
    layer in :mod:`strands_compose.wire`.

    Attributes:
        type: Event type identifier (one of the :class:`EventType` values).
        agent_name: Name of the agent or session entry point that produced
            this event.
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


# ── Session Manifest Models ──────────────────────────────────────────────────


class NodeRef(BaseModel):
    """Reference to a node in an orchestration topology.

    Attributes:
        id: The node identifier (node_id for swarm/graph nodes).
        kind: The node kind ("agent" or "orchestration").
    """

    id: str
    kind: str


class EdgeRef(BaseModel):
    """Reference to a directed edge in a graph orchestration.

    Attributes:
        from_id: The source node identifier.
        to_id: The target node identifier.
    """

    from_id: str
    to_id: str


class ModelDescriptor(BaseModel):
    """Descriptor for an agent's model and provider.

    Attributes:
        model_id: The model identifier (e.g. "us.anthropic.claude-sonnet-4-6"),
            or None if not available.
        provider: The fully-qualified class name of the model provider.
    """

    model_id: str | None
    provider: str


class FileProviderDescriptor(BaseModel):
    """Session manager descriptor for file-based storage.

    Attributes:
        provider: Literal "file".
        session_id: The session identifier.
        storage_dir: The filesystem directory where sessions are stored.
    """

    provider: Literal["file"]
    session_id: str
    storage_dir: str


class S3ProviderDescriptor(BaseModel):
    """Session manager descriptor for S3-based storage.

    Attributes:
        provider: Literal "s3".
        session_id: The session identifier.
        bucket: The S3 bucket name.
        prefix: The S3 key prefix (empty string if no prefix).
    """

    provider: Literal["s3"]
    session_id: str
    bucket: str
    prefix: str


class AgentCoreProviderDescriptor(BaseModel):
    """Session manager descriptor for AgentCore Memory storage.

    Attributes:
        provider: Literal "agentcore".
        session_id: The session identifier.
        memory_id: The AgentCore memory identifier.
        actor_id: The AgentCore actor identifier.
    """

    provider: Literal["agentcore"]
    session_id: str
    memory_id: str
    actor_id: str


class CustomProviderDescriptor(BaseModel):
    """Session manager descriptor for custom session manager implementations.

    Attributes:
        provider: Literal "custom".
        session_id: The session identifier, or None if not available.
        class_name: The fully-qualified class name of the session manager.
    """

    provider: Literal["custom"]
    session_id: str | None
    class_name: str


SessionManagerDescriptor = Annotated[
    FileProviderDescriptor
    | S3ProviderDescriptor
    | AgentCoreProviderDescriptor
    | CustomProviderDescriptor,
    Field(discriminator="provider"),
]
"""Discriminated union of session manager descriptors by provider type."""


class AgentDescriptor(BaseModel):
    """Descriptor for a configured agent in the session.

    Attributes:
        name: The agent's configured name.
        description: The agent's description, or None.
        model: The agent's model descriptor.
        session_manager: The agent's session manager descriptor, or None.
    """

    name: str
    description: str | None
    model: ModelDescriptor
    session_manager: SessionManagerDescriptor | None


class OrchestrationDescriptor(BaseModel):
    """Descriptor for a configured orchestration in the session.

    Attributes:
        name: The orchestration's configured name.
        kind: The orchestration kind ("delegate", "swarm", "graph", or "unknown").
        session_manager: The orchestration's session manager descriptor, or None.
        nodes: List of nodes in the orchestration topology.
        edges: List of edges in the orchestration topology (None for swarm/delegate).
        entry_node_id: The entry node identifier(s), or None.
    """

    name: str
    kind: str
    session_manager: SessionManagerDescriptor | None
    nodes: list[NodeRef] = Field(default_factory=list)
    edges: list[EdgeRef] | None = None
    entry_node_id: str | None = None


class EntryDescriptor(BaseModel):
    """Descriptor identifying the session entry point.

    Attributes:
        name: The entry point's configured name.
        kind: The entry point kind ("agent" or "orchestration").
    """

    name: str
    kind: str


class SessionManifest(BaseModel):
    """Manifest describing the wired session topology and configuration.

    Attributes:
        agents: List of agent descriptors.
        orchestrations: List of orchestration descriptors.
        entry: The entry point descriptor.
    """

    agents: list[AgentDescriptor] = Field(default_factory=list)
    orchestrations: list[OrchestrationDescriptor] = Field(default_factory=list)
    entry: EntryDescriptor
