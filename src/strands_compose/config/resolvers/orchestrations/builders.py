"""Mode-specific orchestration builders — delegate, swarm, graph, and all.

Each builder takes a typed config, a node pool, and an entry name,
then returns the appropriate callable entry point.
``OrchestrationBuilder`` drives the full multi-orchestration build pipeline.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from strands import Agent
from strands.multiagent import GraphBuilder, Swarm

from ....exceptions import ConfigurationError
from ....tools import node_as_async_tool
from ....utils import load_object
from ...schema import (
    DelegateOrchestrationDef,
    GraphOrchestrationDef,
    OrchestrationDef,
    SwarmOrchestrationDef,
)
from ..agents import build_agent_from_def
from ..hooks import resolve_hook_entry
from ..session_manager import resolve_session_manager
from .planner import topological_sort

if TYPE_CHECKING:
    from strands.models import Model
    from strands.multiagent.graph import Graph
    from strands.tools.mcp import MCPClient as StrandsMCPClient

    from ....types import Node
    from ...schema import AgentDef
    from ..session_manager import SessionManager

logger = logging.getLogger(__name__)


class OrchestrationBuilder:
    """Builds all named orchestrations in dependency order."""

    def __init__(
        self,
        configs: dict[str, OrchestrationDef],
        agents: dict[str, Agent],
        agent_defs: dict[str, AgentDef],
        models: dict[str, Model],
        mcp_clients: dict[str, StrandsMCPClient],
        session_manager: SessionManager | None = None,
    ) -> None:
        """Initialize the OrchestrationBuilder.

        Orchestrations are sorted topologically so that each orchestration's
        dependencies (other orchestrations it references) are built first.
        The node pool grows as orchestrations are built, making earlier results
        available to downstream configurations.

        Args:
            configs: Orchestration definitions keyed by name.
            agents: Already-resolved agents keyed by name.
            agent_defs: Agent schema definitions for delegate forking.
            models: Resolved model objects keyed by name.
            mcp_clients: Resolved MCP client objects keyed by name.
            session_manager: Global session manager (may be inherited).
        """
        self._configs = configs
        self._session_manager = session_manager
        self._nodes: dict[str, Node] = dict(agents)
        self._built: dict[str, Node] = {}
        self._agent_defs = agent_defs
        self._models = models
        self._mcp_clients = mcp_clients

    def build_all(self) -> dict[str, Node]:
        """Build all orchestrations in topological order.

        Returns:
            Dict of orchestration name -> built orchestration (Swarm | Graph | Agent).
        """
        for name in topological_sort(self._configs):
            self._build_one(name)
        return self._built

    def _build_one(self, name: str) -> None:
        cfg = self._configs[name]
        entry_name = self._resolve_entry(name, cfg)

        session_manager: SessionManager | None = self._session_manager
        if cfg.session_manager is not None:
            session_manager = resolve_session_manager(cfg.session_manager)

        result = self._dispatch(name, cfg, entry_name, session_manager)
        self._built[name] = result
        self._nodes[name] = result
        logger.info("orchestration=<%s>, mode=<%s> | built orchestration", name, cfg.mode)

    def _resolve_entry(self, name: str, cfg: OrchestrationDef) -> str:
        entry_name = cfg.entry_name
        if entry_name not in self._nodes:
            raise ConfigurationError(
                f"Orchestration '{name}': entry_name '{entry_name}' is not defined.\n"
                f"Available nodes: {sorted(self._nodes)}"
            )
        return entry_name

    def _dispatch(
        self,
        name: str,
        cfg: OrchestrationDef,
        entry_name: str,
        session_manager: SessionManager | None,
    ) -> Agent | Swarm | Graph:
        if isinstance(cfg, DelegateOrchestrationDef):
            return build_delegate(
                name,
                cfg,
                self._nodes,
                entry_name,
                self._agent_defs,
                self._models,
                self._mcp_clients,
                session_manager=session_manager,
            )
        if isinstance(cfg, SwarmOrchestrationDef):
            return build_swarm(
                name,
                cfg,
                self._nodes,
                entry_name,
                session_manager=session_manager,
            )
        if isinstance(cfg, GraphOrchestrationDef):
            return build_graph(
                name,
                cfg,
                self._nodes,
                entry_name,
                session_manager=session_manager,
            )
        raise ConfigurationError(f"Unknown orchestration config type: {type(cfg).__name__}")


def build_delegate(
    name: str,
    config: DelegateOrchestrationDef,
    nodes: dict[str, Node],
    entry_name: str,
    agent_defs: dict[str, AgentDef],
    models: dict[str, Model],
    mcp_clients: dict[str, StrandsMCPClient],
    session_manager: SessionManager | None = None,
) -> Agent:
    """Build delegate orchestration: construct a new Agent with delegate tools.

    A **new** Agent is forked from the entry agent's :class:`AgentDef` blueprint
    (model, system_prompt, hooks, tools, etc.). Each connection is wrapped as
    an async tool and added to the new agent. The original entry agent is
    **never mutated**.

    Args:
        name: Orchestration name (becomes the new agent's name and agent_id).
        config: Delegate orchestration config with connections.
        nodes: Dict of name -> Agent or MultiAgentBase.
        entry_name: Name of the entry agent whose blueprint is forked.
        agent_defs: All declared agent definitions.
        models: Resolved model objects keyed by name.
        mcp_clients: Resolved MCP client objects keyed by name.
        session_manager: Global session manager (may be inherited).

    Returns:
        A **new** Agent with delegate tools registered.

    Raises:
        ConfigurationError: If entry_name is not a declared agent.
    """
    if entry_name not in agent_defs:
        raise ConfigurationError(
            f"Delegate entry '{entry_name}' must be a declared agent, "
            f"not an orchestration or unknown name.\n"
            f"Available agents: {sorted(agent_defs)}"
        )

    # Wrap each connection target as an async delegate tool.
    delegate_tools: list[Any] = []
    for conn in config.connections:
        target_node = nodes[conn.agent]
        delegate_tool = node_as_async_tool(
            target_node,
            description=conn.description,
        )
        delegate_tools.append(delegate_tool)
        logger.info("tool=<%s>, orchestration=<%s> | delegate tool prepared", conn.agent, name)

    # Resolve orchestration-level hooks.
    orch_hooks = [resolve_hook_entry(h) for h in config.hooks]

    # Apply agent_kwargs override: merge entry kwargs with orchestration kwargs.
    entry_def = agent_defs[entry_name]
    if config.agent_kwargs:
        # Merge: entry kwargs first, orchestration kwargs win on conflict.
        entry_def = entry_def.model_copy(
            update={"agent_kwargs": {**entry_def.agent_kwargs, **config.agent_kwargs}}
        )

    # Build a NEW agent from the (possibly overridden) blueprint + delegate tools.
    agent = build_agent_from_def(
        name=name,
        agent_def=entry_def,
        models=models,
        mcp_clients=mcp_clients,
        session_manager=session_manager,
        extra_tools=delegate_tools,
        extra_hooks=orch_hooks,
        session_manager_override=session_manager if config.session_manager is not None else None,
    )

    logger.info(
        "orchestration=<%s>, entry=<%s>, delegates=<%d> | built delegate orchestration",
        name,
        entry_name,
        len(delegate_tools),
    )
    return agent


def build_swarm(
    name: str,
    config: SwarmOrchestrationDef,
    nodes: dict[str, Node],
    entry_name: str,
    session_manager: SessionManager | None = None,
) -> Swarm:
    """Build swarm orchestration using strands Swarm.

    All nodes must be plain Agent instances (strands Swarm limitation).
    Swarm auto-injects ``handoff_to_agent`` tool.

    Args:
        name: Orchestration name (becomes the swarm's id).
        config: Swarm orchestration config.
        nodes: Dict of name -> Agent or MultiAgentBase.
        entry_name: Name of the entry/starting agent.
        session_manager: Optional session manager for the swarm.

    Returns:
        A strands Swarm instance — callable with ``swarm(task)``.

    Raises:
        ConfigurationError: If any referenced node is not an Agent.
    """
    from strands import Agent as _Agent

    node_agents = []
    for agent_name in config.agents:
        node = nodes[agent_name]
        if not isinstance(node, _Agent):
            raise ConfigurationError(
                f"Swarm node '{agent_name}' must be a plain Agent, "
                f"got {type(node).__name__}.\n"
                f"Swarm does not support nested orchestrations — use Graph mode instead."
            )
        node_agents.append(node)

    entry_agent = nodes[entry_name]
    if not isinstance(entry_agent, _Agent):
        raise ConfigurationError(
            f"Swarm entry '{entry_name}' must be a plain Agent, got {type(entry_agent).__name__}."
        )

    hooks = [resolve_hook_entry(h) for h in config.hooks]

    return Swarm(
        id=name,
        nodes=node_agents,
        entry_point=entry_agent,
        max_handoffs=config.max_handoffs,
        max_iterations=config.max_iterations,
        execution_timeout=config.execution_timeout,
        node_timeout=config.node_timeout,
        session_manager=session_manager,
        hooks=hooks,
    )


def build_graph(
    name: str,
    config: GraphOrchestrationDef,
    nodes: dict[str, Node],
    entry_name: str,
    session_manager: SessionManager | None = None,
) -> Graph:
    """Build graph orchestration using strands GraphBuilder.

    Nodes execute in parallel batches based on dependency edges.
    Supports conditional edges, cycles (with ``reset_on_revisit``),
    and nested orchestrations (Swarm/Graph as graph nodes).

    Args:
        name: Orchestration name (becomes the graph's id).
        config: Graph orchestration config with edges.
        nodes: Dict of name -> Agent or MultiAgentBase.
        entry_name: Name of the entry node.
        session_manager: Optional session manager for the graph.

    Returns:
        A strands Graph instance — callable with ``graph(task)``.
    """
    builder = GraphBuilder()
    builder.set_graph_id(name)
    if session_manager is not None:
        builder.set_session_manager(session_manager)

    referenced_nodes: set[str] = {entry_name}
    for edge in config.edges:
        referenced_nodes.add(edge.from_agent)
        referenced_nodes.add(edge.to_agent)

    for node_name in referenced_nodes:
        builder.add_node(nodes[node_name], node_id=node_name)

    for edge_def in config.edges:
        condition = None
        if edge_def.condition:
            condition = load_object(edge_def.condition, target="graph condition")
            if not callable(condition):
                raise ConfigurationError(
                    f"Edge condition '{edge_def.condition}' resolved to a "
                    f"non-callable object ({type(condition).__name__}).\n"
                    f"Conditions must be callable."
                )
        builder.add_edge(
            edge_def.from_agent,
            edge_def.to_agent,
            condition=condition,
        )

    builder.set_entry_point(entry_name)

    if config.hooks:
        builder.set_hook_providers([resolve_hook_entry(h) for h in config.hooks])

    if config.max_node_executions is not None:
        builder.set_max_node_executions(config.max_node_executions)
    if config.execution_timeout is not None:
        builder.set_execution_timeout(config.execution_timeout)
    if config.node_timeout is not None:
        builder.set_node_timeout(config.node_timeout)
    if config.reset_on_revisit:
        builder.reset_on_revisit(True)

    return builder.build()
