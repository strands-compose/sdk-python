"""Config reference validation — checks cross-references before resolution."""

from __future__ import annotations

from ...exceptions import UnresolvedReferenceError
from ..schema import (
    AppConfig,
    DelegateOrchestrationDef,
    GraphOrchestrationDef,
    SwarmOrchestrationDef,
)


def validate_references(config: AppConfig) -> None:
    """Validate that all cross-references in the config are resolvable.

    Checks:
    - Agent model references exist in config.models
    - Agent MCP client references exist in config.mcp_clients
    - MCP client server references exist in config.mcp_servers
    - Orchestration node references exist in agents or orchestrations

    Args:
        config: Validated AppConfig to check.

    Raises:
        ValueError: With clear message about what reference is broken.
    """
    agent_names = set(config.agents)
    orch_names = set(config.orchestrations)
    all_node_names = agent_names | orch_names

    for agent_name, agent_def in config.agents.items():
        if isinstance(agent_def.model, str) and agent_def.model not in config.models:
            raise UnresolvedReferenceError(
                f"Agent '{agent_name}' references model '{agent_def.model}' "
                f"which is not defined.\n"
                f"Available models: {list(config.models)}"
            )
        for mcp_name in agent_def.mcp:
            if mcp_name not in config.mcp_clients:
                raise UnresolvedReferenceError(
                    f"Agent '{agent_name}' references MCP client '{mcp_name}' "
                    f"which is not defined.\n"
                    f"Available: {list(config.mcp_clients)}"
                )

    for client_name, client_def in config.mcp_clients.items():
        if client_def.server and client_def.server not in config.mcp_servers:
            raise UnresolvedReferenceError(
                f"MCP client '{client_name}' references server '{client_def.server}' "
                f"which is not defined.\n"
                f"Available: {list(config.mcp_servers)}"
            )

    for orch_name, orch_def in config.orchestrations.items():
        validate_orchestration_refs(orch_def, all_node_names, orch_name=orch_name)


def validate_orchestration_refs(
    orchestration: DelegateOrchestrationDef | SwarmOrchestrationDef | GraphOrchestrationDef,
    valid_names: set[str],
    orch_name: str | None = None,
) -> None:
    """Validate that all node references in an orchestration exist.

    Args:
        orchestration: The orchestration config section.
        valid_names: Set of valid node names (agents + orchestrations).
        orch_name: Name of this orchestration (for error messages).

    Raises:
        ValueError: With clear message about broken reference.
    """
    prefix = f"Orchestration '{orch_name}': " if orch_name else ""

    if isinstance(orchestration, DelegateOrchestrationDef):
        if orchestration.entry_name not in valid_names:
            raise UnresolvedReferenceError(
                f"{prefix}entry_name '{orchestration.entry_name}' is not defined.\n"
                f"Available: {sorted(valid_names)}"
            )
        for conn in orchestration.connections:
            if conn.agent not in valid_names:
                raise UnresolvedReferenceError(
                    f"{prefix}Delegate target '{conn.agent}' is not defined.\n"
                    f"Available: {sorted(valid_names)}"
                )
            if conn.agent == orchestration.entry_name:
                raise UnresolvedReferenceError(
                    f"{prefix}Agent '{orchestration.entry_name}' delegates to itself — "
                    f"circular delegation is not allowed."
                )

    elif isinstance(orchestration, SwarmOrchestrationDef):
        if orchestration.entry_name not in valid_names:
            raise UnresolvedReferenceError(
                f"{prefix}entry_name '{orchestration.entry_name}' is not defined.\n"
                f"Available: {sorted(valid_names)}"
            )
        for agent_name in orchestration.agents:
            if agent_name not in valid_names:
                raise UnresolvedReferenceError(
                    f"{prefix}Swarm agent '{agent_name}' is not defined.\n"
                    f"Available: {sorted(valid_names)}"
                )

    elif isinstance(orchestration, GraphOrchestrationDef):
        if orchestration.entry_name not in valid_names:
            raise UnresolvedReferenceError(
                f"{prefix}entry_name '{orchestration.entry_name}' is not defined.\n"
                f"Available: {sorted(valid_names)}"
            )
        for edge in orchestration.edges:
            if edge.from_agent not in valid_names:
                raise UnresolvedReferenceError(
                    f"{prefix}Graph edge source '{edge.from_agent}' is not defined.\n"
                    f"Available: {sorted(valid_names)}"
                )
            if edge.to_agent not in valid_names:
                raise UnresolvedReferenceError(
                    f"{prefix}Graph edge target '{edge.to_agent}' is not defined.\n"
                    f"Available: {sorted(valid_names)}"
                )
