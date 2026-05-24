"""Build session manifests from resolved runtime objects.

A :class:`~strands_compose.types.SessionManifest` describes the wired session
topology, model/provider info, and storage locations.  It is constructed from
runtime ``strands.Agent``, ``Swarm``, ``Graph``, and ``SessionManager``
instances at invocation time and serialised into the SESSION_START event
payload.

Both public functions in this module are pure: no I/O, no network calls, no
mutation of inputs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from strands import Agent
from strands.multiagent import Swarm
from strands.multiagent.graph import Graph
from strands.session import FileSessionManager, S3SessionManager

from .types import (
    AgentCoreProviderDescriptor,
    AgentDescriptor,
    CustomProviderDescriptor,
    EdgeRef,
    EntryDescriptor,
    FileProviderDescriptor,
    ModelDescriptor,
    NodeRef,
    OrchestrationDescriptor,
    S3ProviderDescriptor,
    SessionManagerDescriptor,
    SessionManifest,
)

if TYPE_CHECKING:
    from strands.session import SessionManager

    from .types import Node


logger = logging.getLogger(__name__)


# ── Session manager descriptors ──────────────────────────────────────────────


def build_session_manager_descriptor(manager: SessionManager) -> SessionManagerDescriptor:
    """Build a :class:`SessionManagerDescriptor` from a SessionManager instance.

    Selection order:

    1. :class:`strands.session.FileSessionManager` → ``FileProviderDescriptor``
    2. :class:`strands.session.S3SessionManager` → ``S3ProviderDescriptor``
    3. Duck-typed AgentCore (``manager.config`` carries ``memory_id``,
       ``actor_id``, ``session_id``) → ``AgentCoreProviderDescriptor``
    4. Fallback → ``CustomProviderDescriptor``

    The function is pure: no I/O, no mutation.  It reads only public attributes
    on the manager and the class's ``__module__``/``__qualname__`` for the
    custom fallback.

    Args:
        manager: A strands ``SessionManager`` instance.

    Returns:
        A :class:`SessionManagerDescriptor` (one of the four concrete subtypes).

    Raises:
        AttributeError: If a required attribute is missing on a ``File`` or
            ``S3`` manager (indicates a broken strands install).
    """
    if isinstance(manager, FileSessionManager):
        return FileProviderDescriptor(
            provider="file",
            session_id=manager.session_id,
            storage_dir=manager.storage_dir,
        )

    if isinstance(manager, S3SessionManager):
        return S3ProviderDescriptor(
            provider="s3",
            session_id=manager.session_id,
            bucket=manager.bucket,
            prefix=manager.prefix,
        )

    config = getattr(manager, "config", None)
    if config is not None and all(
        hasattr(config, attr) for attr in ("memory_id", "actor_id", "session_id")
    ):
        return AgentCoreProviderDescriptor(
            provider="agentcore",
            session_id=str(config.session_id),
            memory_id=str(config.memory_id),
            actor_id=str(config.actor_id),
        )

    return CustomProviderDescriptor(
        provider="custom",
        session_id=getattr(manager, "session_id", None),
        class_name=f"{type(manager).__module__}.{type(manager).__qualname__}",
    )


def _descriptor_or_none(
    manager: SessionManager | None,
) -> SessionManagerDescriptor | None:
    """Return the descriptor for *manager*, or ``None`` if no manager is set."""
    if manager is None:
        return None
    return build_session_manager_descriptor(manager)


# ── Agent descriptor ─────────────────────────────────────────────────────────


def _model_descriptor(agent: Agent) -> ModelDescriptor:
    """Extract a :class:`ModelDescriptor` from an agent's model."""
    config = agent.model.get_config()
    if isinstance(config, dict):
        model_id = config.get("model_id")
    else:
        model_id = getattr(config, "model_id", None)
    return ModelDescriptor(
        model_id=model_id,
        provider=f"{type(agent.model).__module__}.{type(agent.model).__qualname__}",
    )


def _agent_descriptor(name: str, agent: Agent) -> AgentDescriptor:
    """Build an :class:`AgentDescriptor` for a single resolved agent."""
    return AgentDescriptor(
        name=name,
        description=agent.description,
        model=_model_descriptor(agent),
        session_manager=_descriptor_or_none(agent._session_manager),
    )


# ── Orchestration descriptor ─────────────────────────────────────────────────


def _swarm_topology(swarm: Swarm) -> tuple[list[NodeRef], None, str | None]:
    """Extract (nodes, edges, entry_node_id) from a Swarm.

    Swarm handoffs are dynamic, so ``edges`` is always ``None``.
    """
    nodes = [NodeRef(id=node.node_id, kind="agent") for node in swarm.nodes.values()]

    entry_id: str | None = None
    if swarm.entry_point is not None:
        for node in swarm.nodes.values():
            if node.executor is swarm.entry_point:
                entry_id = node.node_id
                break
    elif swarm.nodes:
        entry_id = next(iter(swarm.nodes.values())).node_id

    return nodes, None, entry_id


def _graph_topology(graph: Graph) -> tuple[list[NodeRef], list[EdgeRef], str | None]:
    """Extract (nodes, edges, entry_node_id) from a Graph."""
    nodes = [
        NodeRef(
            id=node.node_id,
            kind="agent" if isinstance(node.executor, Agent) else "orchestration",
        )
        for node in graph.nodes.values()
    ]
    edges = [
        EdgeRef(from_id=edge.from_node.node_id, to_id=edge.to_node.node_id) for edge in graph.edges
    ]

    entry_points = list(graph.entry_points)
    if len(entry_points) == 1:
        entry_id: str | None = entry_points[0].node_id
    elif len(entry_points) > 1:
        entry_id = ",".join(node.node_id for node in entry_points)
    else:
        entry_id = None

    return nodes, edges, entry_id


def _orchestration_descriptor(name: str, orch: Node) -> OrchestrationDescriptor:
    """Build an :class:`OrchestrationDescriptor` for a single orchestration.

    Dispatches by runtime type:

    * :class:`strands.Agent` (delegate) → ``kind="delegate"``, empty topology
    * :class:`strands.multiagent.Swarm` → ``kind="swarm"``, swarm topology
    * :class:`strands.multiagent.graph.Graph` → ``kind="graph"``, graph topology
    * any other type → ``kind="unknown"``, empty topology
    """
    if isinstance(orch, Agent):
        return OrchestrationDescriptor(
            name=name,
            kind="delegate",
            session_manager=_descriptor_or_none(orch._session_manager),
        )

    if isinstance(orch, Swarm):
        nodes, edges, entry_id = _swarm_topology(orch)
        return OrchestrationDescriptor(
            name=name,
            kind="swarm",
            session_manager=_descriptor_or_none(getattr(orch, "session_manager", None)),
            nodes=nodes,
            edges=edges,
            entry_node_id=entry_id,
        )

    if isinstance(orch, Graph):
        nodes, edges, entry_id = _graph_topology(orch)
        return OrchestrationDescriptor(
            name=name,
            kind="graph",
            session_manager=_descriptor_or_none(getattr(orch, "session_manager", None)),
            nodes=nodes,
            edges=edges,
            entry_node_id=entry_id,
        )

    return OrchestrationDescriptor(
        name=name,
        kind="unknown",
        session_manager=_descriptor_or_none(getattr(orch, "session_manager", None)),
    )


# ── Entry resolution ─────────────────────────────────────────────────────────


def _resolve_entry(
    entry: Node,
    agents: dict[str, Agent],
    orchestrators: dict[str, Node],
) -> EntryDescriptor:
    """Reverse-lookup *entry* in *agents* then *orchestrators* by object identity.

    Raises:
        ValueError: If *entry* is not found in either dict.
    """
    for name, agent in agents.items():
        if agent is entry:
            return EntryDescriptor(name=name, kind="agent")
    for name, orch in orchestrators.items():
        if orch is entry:
            return EntryDescriptor(name=name, kind="orchestration")
    raise ValueError(
        f"entry_type=<{type(entry).__name__}> | entry node not found in agents or orchestrators"
    )


# ── Public API ───────────────────────────────────────────────────────────────


def build_manifest(
    agents: dict[str, Agent],
    orchestrators: dict[str, Node],
    entry: Node,
) -> SessionManifest:
    """Build a :class:`SessionManifest` from resolved runtime objects.

    Pure function: no I/O, no network calls, no mutation of inputs.

    Args:
        agents: Resolved agents keyed by name.
        orchestrators: Resolved orchestrations keyed by name.
        entry: The entry point node (must be one of the values in *agents* or
            *orchestrators* by object identity).

    Returns:
        A complete :class:`SessionManifest` with all fields populated.

    Raises:
        ValueError: If *entry* cannot be resolved by object identity.
    """
    return SessionManifest(
        agents=[_agent_descriptor(name, agent) for name, agent in agents.items()],
        orchestrations=[
            _orchestration_descriptor(name, orch) for name, orch in orchestrators.items()
        ],
        entry=_resolve_entry(entry, agents, orchestrators),
    )


def first_session_id(manifest: SessionManifest) -> str | None:
    """Return the first non-None ``session_id`` found in the manifest.

    Iterates ``manifest.agents`` first, then ``manifest.orchestrations``,
    returning the first ``session_manager.session_id`` that is set.  Used by
    :meth:`ResolvedConfig.wire_event_queue` to determine the effective session
    id for the SESSION_END event payload.

    Args:
        manifest: The session manifest.

    Returns:
        The first session id found, or ``None`` when no descriptor in the
        manifest has a session manager set.
    """
    for descriptor in (*manifest.agents, *manifest.orchestrations):
        if descriptor.session_manager is not None:
            return descriptor.session_manager.session_id
    return None
