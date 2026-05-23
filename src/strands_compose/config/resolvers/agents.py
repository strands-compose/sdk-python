"""Resolve AgentDef -> strands Agent instances and orchestration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from strands import Agent

from ...exceptions import ConfigurationError
from ...utils import load_object
from .conversation_manager import resolve_conversation_manager
from .hooks import resolve_hook_entry
from .mcp import resolve_tools
from .models import resolve_model
from .session_manager import resolve_leaf_session_manager

if TYPE_CHECKING:
    from strands.agent.conversation_manager import ConversationManager
    from strands.models import Model
    from strands.session.session_manager import SessionManager
    from strands.tools.mcp import MCPClient as StrandsMCPClient

    from ..schema import AgentDef, SessionManagerDef

logger = logging.getLogger(__name__)


def build_agent_from_def(
    name: str,
    agent_def: AgentDef,
    models: dict[str, Model],
    mcp_clients: dict[str, StrandsMCPClient],
    *,
    global_session_manager_def: SessionManagerDef | None = None,
    session_id: str | None = None,
    extra_tools: list[Any] | None = None,
    extra_hooks: list[Any] | None = None,
    orchestration_agent_names: set[str] | None = None,
) -> Agent:
    """Build a single Agent from an AgentDef blueprint.

    This is the canonical way to construct an agent from its YAML definition.
    Used by both :func:`resolve_agents` (to build all declared agents) and
    by :func:`~strands_compose.config.resolvers.orchestrations.builders.build_delegate`
    (to fork an agent with delegate tools).

    Args:
        name: Agent name / agent_id.
        agent_def: The agent's schema definition.
        models: Resolved model objects keyed by name.
        mcp_clients: Resolved MCP client objects keyed by name.
        global_session_manager_def: Global session manager def from
            ``AppConfig.session_manager``, used as a fallback when the agent
            declares no ``session_manager:`` of its own and has not explicitly
            opted out (``session_manager: ~``).
        session_id: Effective session id threaded down from ``load_session``.
            Passed as ``session_id_override`` to every
            ``resolve_session_manager`` call made in this function.
        extra_tools: Additional tools to append (e.g. delegate tools).
        extra_hooks: Additional hooks to append (e.g. orchestration-level hooks).
        orchestration_agent_names: Agent names in swarm/graph orchestrations (fail-fast on SM).

    Returns:
        A freshly constructed strands Agent.

    Raises:
        ConfigurationError: If a swarm or graph agent has a session manager.
        TypeError: If a custom factory doesn't return an Agent.
    """
    # 1. Resolve model — inline ModelDef or global name ref
    model: Model | None = None
    if agent_def.model is not None:
        if isinstance(agent_def.model, str):
            model = models[agent_def.model]
        else:
            model = resolve_model(agent_def.model)

    # 2. Resolve tool specs
    tools = resolve_tools(agent_def.tools)

    # 3. Resolve hooks — module:ClassName or inline HookDef
    hooks = [resolve_hook_entry(h) for h in agent_def.hooks]

    # 4. MCP clients as tool providers
    tool_providers: list[Any] = [mcp_clients[n] for n in agent_def.mcp]

    # 5. Resolve session manager (uniform leaf chain).
    #   1. agent_def.session_manager set        → resolve it (per-agent override)
    #   2. agent_def explicit opt-out (None)    → None
    #   3. global_session_manager_def set       → resolve it (inherited global)
    #   4. otherwise                            → None
    agent_session: SessionManager | None = resolve_leaf_session_manager(
        leaf_def=agent_def.session_manager,
        leaf_is_set="session_manager" in agent_def.model_fields_set,
        global_def=global_session_manager_def,
        session_id=session_id,
    )

    # Fail fast: swarm/graph node agents cannot carry a session manager.
    if (
        orchestration_agent_names
        and name in orchestration_agent_names
        and agent_session is not None
    ):
        source = (
            "per-agent 'session_manager:' field"
            if agent_def.session_manager is not None
            else "global 'session_manager:' in config"
        )
        raise ConfigurationError(
            f"Agent '{name}' is in a swarm or graph orchestration and cannot have a session manager "
            f"(source: {source}).\n"
            "Strands does not yet support session persistence for Swarm or Graph node agents.\n"
            f"Fix: Add 'session_manager: ~' to agent '{name}' to opt out of the global default."
        )

    # 6. Resolve conversation manager
    conversation_manager: ConversationManager | None = None
    if agent_def.conversation_manager is not None:
        conversation_manager = resolve_conversation_manager(agent_def.conversation_manager)

    # 7. Build the agent
    all_tools = tools + tool_providers + (extra_tools or [])
    all_hooks = hooks + (extra_hooks or [])

    if agent_def.type is not None:
        factory = load_object(agent_def.type, target="agent factory")
        agent = factory(
            name=name,
            agent_id=name,
            model=model,
            system_prompt=agent_def.system_prompt,
            description=agent_def.description,
            tools=all_tools,
            hooks=all_hooks,
            conversation_manager=conversation_manager,
            session_manager=agent_session,
            **agent_def.agent_kwargs,
        )
    else:
        agent = Agent(
            name=name,
            agent_id=name,
            model=model,
            system_prompt=agent_def.system_prompt,
            description=agent_def.description,
            tools=all_tools,
            hooks=all_hooks,
            conversation_manager=conversation_manager,
            session_manager=agent_session,
            load_tools_from_directory=False,
            **agent_def.agent_kwargs,
        )

    if not isinstance(agent, Agent):
        raise TypeError(
            f"Agent factory for '{name}' returned {type(agent).__name__}, expected strands.Agent."
        )

    return agent


def resolve_agents(
    agent_defs: dict[str, AgentDef],
    models: dict[str, Model],
    mcp_clients: dict[str, StrandsMCPClient],
    *,
    global_session_manager_def: SessionManagerDef | None = None,
    session_id: str | None = None,
    orchestration_agent_names: set[str] | None = None,
) -> dict[str, Agent]:
    """Resolve all agents -- flat, no dependencies between them.

    Each agent is independent.  They reference models, MCP clients, and
    sessions -- but NOT other agents.  Agent-to-agent wiring is handled by
    the orchestration step.

    ``hooks`` entries are either import-path strings
    (``module.path:ClassName`` or ``./file.py:ClassName``) or inline HookDef
    objects -- resolved per-agent so each agent gets fresh hook instances.

    Args:
        agent_defs: Agent definitions keyed by name.
        models: Resolved model instances keyed by name.
        mcp_clients: Resolved MCP clients keyed by name.
        global_session_manager_def: Global session manager def from
            ``AppConfig.session_manager``, used as a fallback when an agent
            declares no ``session_manager:`` of its own and has not explicitly
            opted out (``session_manager: ~``).
        session_id: Effective session id threaded down from ``load_session``.
            Passed as ``session_id_override`` to every
            ``resolve_session_manager`` call made in this function.
        orchestration_agent_names: Names of agents in swarm or graph orchestrations
            (these agents must not have a session manager).

    Returns:
        Resolved agents dict keyed by name.

    Raises:
        ConfigurationError if an agent used in a Swarm or Graph orchestration has a session manager assigned.
        TypeError if agent factory does not return a strands Agent instance.
    """
    resolved: dict[str, Agent] = {}

    for name, agent_def in agent_defs.items():
        agent = build_agent_from_def(
            name=name,
            agent_def=agent_def,
            models=models,
            mcp_clients=mcp_clients,
            global_session_manager_def=global_session_manager_def,
            session_id=session_id,
            orchestration_agent_names=orchestration_agent_names,
        )
        resolved[name] = agent
        logger.info("agent=<%s>, type=<%s> | resolved agent", name, agent_def.type or "Agent")

    return resolved
