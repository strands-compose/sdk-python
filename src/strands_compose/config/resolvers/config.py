"""ResolvedConfig, ResolvedInfra, and resolve_infra orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...manifest import build_manifest
from ...mcp.lifecycle import MCPLifecycle
from ...wire import make_event_queue
from .mcp import resolve_mcp_client, resolve_mcp_server
from .models import resolve_model

if TYPE_CHECKING:
    from strands import Agent
    from strands.models import Model
    from strands.tools.mcp import MCPClient as StrandsMCPClient

    from ...mcp.server import MCPServer
    from ...types import Node
    from ...wire import EventQueue
    from ..schema import AppConfig

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ResolvedConfig:
    """Fully resolved config — lifecycle started, agents ready.

    After calling :func:`~strands_compose.config.loaders.load`, use
    :meth:`wire_event_queue` to set up event streaming::

        resolved = load("config.yaml")
        event_queue = resolved.wire_event_queue()
    """

    agents: dict[str, Agent] = field(default_factory=dict)
    orchestrators: dict[str, Node] = field(default_factory=dict)
    entry: Node
    mcp_lifecycle: MCPLifecycle = field(default_factory=MCPLifecycle)

    def wire_event_queue(
        self,
        *,
        session_id: str | None = None,
        tool_labels: dict[str, str] | None = None,
    ) -> EventQueue:
        """Wire all agents and orchestrators for event streaming.

        This is the recommended way to set up event streaming.  It:

        1. Builds a :class:`~strands_compose.types.SessionManifest` from the
           resolved runtime objects.
        2. Wires every agent (and orchestrator) with an
           :class:`~strands_compose.hooks.EventPublisher` via
           :func:`~strands_compose.wire.make_event_queue`.
        3. Emits a SESSION_START event carrying the manifest as the first
           event on the queue.

        .. warning::

            This **mutates** the agents and orchestrators stored on this
            instance by adding hooks and overwriting ``callback_handler``.
            Call it only once per ``ResolvedConfig`` instance.

        Args:
            session_id: Optional session ID to embed in events.
            tool_labels: Optional tool name → display label mapping.

        Returns:
            A ready-to-use :class:`~strands_compose.wire.EventQueue` with
            SESSION_START already on it.

        Raises:
            ValueError: If the entry node cannot be resolved by object identity.
        """
        manifest = build_manifest(self.agents, self.orchestrators, self.entry)
        event_queue = make_event_queue(
            self.agents,
            orchestrators=self.orchestrators,
            tool_labels=tool_labels,
            entry_name=manifest.entry.name,
            session_id=session_id,
        )
        event_queue.emit_session_start(manifest)
        return event_queue


@dataclass
class ResolvedInfra:
    """Infrastructure resolved from config — lifecycle NOT started.

    This is the pure result of :func:`resolve_infra`.  Lifecycle is cold,
    agents are not yet created.

    Session managers are NOT stored here — they are built per agent and per
    orchestration at session time, from ``config.session_manager`` (the global
    def) plus ``effective_session_id`` computed by ``load_session``.

    Use :func:`~strands_compose.config.loaders.load` for a fully
    activated system, or manually::

        infra = resolve_infra(config)
        infra.mcp_lifecycle.start()
        agents = resolve_agents(agent_defs=config.agents, ...)
    """

    models: dict[str, Model] = field(default_factory=dict)
    clients: dict[str, StrandsMCPClient] = field(default_factory=dict)
    mcp_lifecycle: MCPLifecycle = field(default_factory=MCPLifecycle)


def resolve_infra(config: AppConfig) -> ResolvedInfra:
    """Resolve infrastructure from an AppConfig (pure, no I/O).

    Creates model objects, MCP server/client objects, and a lifecycle
    manager.  Nothing is started.

    Resolution order:

    1. Models (no dependencies)
    2. MCP servers (no dependencies)
    3. MCP clients (depend on servers)
    4. MCP lifecycle (assembles servers + clients, **not** started)
    5. Session manager validation only — ``agentcore`` provider rejected
       globally; no instance is constructed (instances are built per-leaf
       at session time).

    Agents and orchestration are resolved in :func:`load` after
    ``mcp_lifecycle.start()`` because ``Agent.__init__`` auto-starts
    MCP clients which need servers to be running first.  The lifecycle
    start in ``load()`` is idempotent — the context manager is still
    used for graceful shutdown.

    Args:
        config: Parsed AppConfig from YAML.

    Returns:
        A :class:`ResolvedInfra` with models, clients, and a cold MCP lifecycle.
    """
    # Models
    models: dict[str, Model] = {}
    for name, model_def in config.models.items():
        models[name] = resolve_model(model_def)
        logger.info("model=<%s>, provider=<%s> | resolved model", name, model_def.provider)

    # MCP servers
    servers: dict[str, MCPServer] = {}
    for name, server_def in config.mcp_servers.items():
        servers[name] = resolve_mcp_server(server_def, name=name)
        logger.info("server=<%s> | resolved MCP server", name)

    # MCP clients (resolved but NOT started)
    clients: dict[str, StrandsMCPClient] = {}
    for name, client_def in config.mcp_clients.items():
        clients[name] = resolve_mcp_client(client_def, servers, name=name)
        logger.info("client=<%s> | resolved MCP client", name)

    # MCP lifecycle (cold — not started)
    lifecycle = MCPLifecycle()
    for name, server in servers.items():
        lifecycle.add_server(name, server)
    for name, client in clients.items():
        lifecycle.add_client(name, client)

    # Session manager — validation only
    # Instances are built per leaf in load_session / agents / orchestrations.
    # Provider 'agentcore' cannot be set globally -
    # it requires a unique 'actor_id' per agent. Fail fast at boot.
    if (
        config.session_manager is not None
        and config.session_manager.provider.lower() == "agentcore"
    ):
        raise ValueError(
            "The 'agentcore' session manager cannot be set globally.\n"
            "Configure it per-agent — 'actor_id' must be unique per agent."
        )

    return ResolvedInfra(
        models=models,
        clients=clients,
        mcp_lifecycle=lifecycle,
    )
