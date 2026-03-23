"""ResolvedConfig, ResolvedInfra, and resolve_infra orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...mcp.lifecycle import MCPLifecycle
from ...wire import make_event_queue
from .mcp import resolve_mcp_client, resolve_mcp_server
from .models import resolve_model
from .session_manager import resolve_session_manager

if TYPE_CHECKING:
    from strands import Agent
    from strands.models import Model
    from strands.session.session_manager import SessionManager
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
        tool_labels: dict[str, str] | None = None,
    ) -> EventQueue:
        """Wire all agents and orchestrators for event streaming.

        This is the recommended way to set up event streaming.  It calls
        :func:`~strands_compose.wire.make_event_queue` with this
        config's agents and orchestrators.

        .. warning::

            This **mutates** the agents and orchestrators stored on this
            instance by adding hooks and overwriting ``callback_handler``.
            Call it only once per ``ResolvedConfig`` instance.

        Args:
            tool_labels: Optional tool name -> display label mapping.

        Returns:
            A ready-to-use :class:`~strands_compose.wire.EventQueue`.
        """
        return make_event_queue(
            self.agents,
            orchestrators=self.orchestrators,
            tool_labels=tool_labels,
        )


@dataclass
class ResolvedInfra:
    """Infrastructure resolved from config — lifecycle NOT started.

    This is the pure result of :func:`resolve_infra`.  Lifecycle is cold,
    agents are not yet created.

    Use :func:`~strands_compose.config.loaders.load` for a fully
    activated system, or manually::

        infra = resolve_infra(config)
        infra.mcp_lifecycle.start()
        agents = resolve_agents(agent_defs=config.agents, ...)
    """

    models: dict[str, Model] = field(default_factory=dict)
    clients: dict[str, StrandsMCPClient] = field(default_factory=dict)
    session_manager: SessionManager | None = None
    mcp_lifecycle: MCPLifecycle = field(default_factory=MCPLifecycle)


def resolve_infra(config: AppConfig) -> ResolvedInfra:
    """Resolve infrastructure from an AppConfig (pure, no I/O).

    Creates model objects, MCP server/client objects, a lifecycle
    manager, and a session manager.  Nothing is started.

    Resolution order:

    1. Models (no dependencies)
    2. MCP servers (no dependencies)
    3. MCP clients (depend on servers)
    4. MCP lifecycle (assembles servers + clients, **not** started)
    5. Session manager (no dependencies)

    Agents and orchestration are resolved in :func:`load` after
    ``mcp_lifecycle.start()`` because ``Agent.__init__`` auto-starts
    MCP clients which need servers to be running first.  The lifecycle
    start in ``load()`` is idempotent — the context manager is still
    used for graceful shutdown.

    Args:
        config: Parsed AppConfig from YAML.

    Returns:
        A :class:`ResolvedInfra` with models, clients, session manager,
        and a cold MCP lifecycle.
    """
    # 1. Models
    models: dict[str, Model] = {}
    for name, model_def in config.models.items():
        models[name] = resolve_model(model_def)
        logger.info("model=<%s>, provider=<%s> | resolved model", name, model_def.provider)

    # 2. MCP servers
    servers: dict[str, MCPServer] = {}
    for name, server_def in config.mcp_servers.items():
        servers[name] = resolve_mcp_server(server_def, name=name)
        logger.info("server=<%s> | resolved MCP server", name)

    # 3. MCP clients (resolved but NOT started)
    clients: dict[str, StrandsMCPClient] = {}
    for name, client_def in config.mcp_clients.items():
        clients[name] = resolve_mcp_client(client_def, servers, name=name)
        logger.info("client=<%s> | resolved MCP client", name)

    # 4. MCP lifecycle (cold — not started)
    lifecycle = MCPLifecycle()
    for name, server in servers.items():
        lifecycle.add_server(name, server)
    for name, client in clients.items():
        lifecycle.add_client(name, client)

    # 5. Session manager
    session_manager: SessionManager | None = None
    if config.session_manager is not None:
        # Prevent AgentCoreMemorySessionManager from being set globally
        # Required "actor_id" param makes it unsuitable for global config
        if config.session_manager.provider.lower() == "agentcore":
            raise ValueError(
                "The 'agentcore' session manager cannot be set globally.\n"
                "Configure it for each agent - required 'actor_id' param."
            )
        session_manager = resolve_session_manager(config.session_manager)
        logger.info("provider=<%s> | resolved session manager", config.session_manager.provider)

    return ResolvedInfra(
        models=models,
        clients=clients,
        session_manager=session_manager,
        mcp_lifecycle=lifecycle,
    )
