"""Orchestration package — wires agents together in delegate, swarm, or graph mode.

Supports both flat (single orchestration) and nested (named orchestrations
that reference each other) configurations.  Node references in delegate
connections, swarm agents, and graph edges can point to either an agent name
or a named orchestration.

Submodules
----------
_tools      node_as_tool / node_as_async_tool wrappers
_builders   Mode-specific builders (delegate, swarm, graph)
_planner    Dependency resolution & multi-orchestration build
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....tools import node_as_async_tool, node_as_tool
from .builders import (
    OrchestrationBuilder,
    build_delegate,
    build_graph,
    build_swarm,
)

if TYPE_CHECKING:
    from strands import Agent
    from strands.models import Model
    from strands.tools.mcp import MCPClient as StrandsMCPClient

    from ....types import Node
    from ...schema import AgentDef, AppConfig
    from ..session_manager import SessionManager


def resolve_orchestrations(
    config: AppConfig,
    agents: dict[str, Agent],
    agent_defs: dict[str, AgentDef],
    models: dict[str, Model],
    mcp_clients: dict[str, StrandsMCPClient],
    session_manager: SessionManager | None = None,
) -> dict[str, Node]:
    """Build all named orchestrations from config.

    Args:
        config: Full application config containing orchestration definitions.
        agents: Resolved agent instances keyed by name.
        agent_defs: Agent definition models keyed by name.
        models: Resolved model instances keyed by name.
        mcp_clients: Resolved MCP clients keyed by name.
        session_manager: Optional shared session manager.

    Returns:
        Dict of orchestration name -> built Swarm/Graph/Agent.
        Empty dict when no orchestrations are defined.
    """
    if not config.orchestrations:
        return {}

    return OrchestrationBuilder(
        config.orchestrations,
        agents,
        agent_defs,
        models,
        mcp_clients,
        session_manager,
    ).build_all()


__all__ = [
    "OrchestrationBuilder",
    "build_delegate",
    "build_graph",
    "build_swarm",
    "node_as_async_tool",
    "node_as_tool",
    "resolve_orchestrations",
]
