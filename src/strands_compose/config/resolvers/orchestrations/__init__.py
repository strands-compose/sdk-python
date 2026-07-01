"""Orchestration package — wires agents together in delegate, swarm, or graph mode.

Supports both flat (single orchestration) and nested (named orchestrations
that reference each other) configurations.  Node references in delegate
connections, swarm agents, and graph edges can point to either an agent name
or a named orchestration.
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
    from ...schema import AgentDef, AppConfig, SessionManagerDef


def resolve_orchestrations(
    config: AppConfig,
    agents: dict[str, Agent],
    agent_defs: dict[str, AgentDef],
    models: dict[str, Model],
    mcp_clients: dict[str, StrandsMCPClient],
    *,
    global_session_manager_def: SessionManagerDef | None = None,
    session_id: str | None = None,
) -> dict[str, Node]:
    """Build all named orchestrations from config.

    Args:
        config: Full application config containing orchestration definitions.
        agents: Resolved agent instances keyed by name.
        agent_defs: Agent definition models keyed by name.
        models: Resolved model instances keyed by name.
        mcp_clients: Resolved MCP clients keyed by name.
        global_session_manager_def: Global session manager def from
            ``AppConfig.session_manager``, used as a fallback when an
            orchestration declares no ``session_manager:`` of its own.
        session_id: Effective session id threaded down from ``load_session``.
            Passed as ``session_id_override`` to every
            ``resolve_session_manager`` call made by leaf builders.

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
        global_session_manager_def=global_session_manager_def,
        session_id=session_id,
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
