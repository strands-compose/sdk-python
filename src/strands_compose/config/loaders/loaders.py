"""Public loading functions — parse YAML config and resolve to live objects.

Usage::

    from strands_compose.config import load

    # Single file
    resolved = load("config.yaml")

    # Multiple files (merged)
    resolved = load(["agents.yaml", "mcp.yaml"])

    # Raw YAML string
    resolved = load("agents:\\n  a:\\n    system_prompt: hi")

    with resolved.mcp_lifecycle:
        result = resolved.entry("Hello!")

Key Features:
    - Single-file and multi-file config loading with automatic merging
    - Per-source variable interpolation and anchor stripping
    - Automatic MCP server startup before agent creation
    - Session-level isolation for multi-tenant server deployments
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import ValidationError

from ...exceptions import SchemaValidationError
from ..resolvers import (
    ResolvedConfig,
    ResolvedInfra,
    resolve_agents,
    resolve_infra,
    resolve_orchestrations,
    resolve_session_manager,
)
from ..schema import AppConfig, SwarmOrchestrationDef
from .helpers import merge_raw_configs, parse_single_source, sanitize_collection_keys
from .validators import validate_references

logger = logging.getLogger(__name__)

# Single config source: file path (``str`` or ``Path``) or raw YAML string.
ConfigInput = str | Path


def normalize(raw: dict) -> dict:
    """Run schema version migrations.

    Called before ``AppConfig.model_validate()`` to allow forward-compatible
    schema evolution.  Currently only version ``"1"`` is supported.

    Args:
        raw: The merged raw config dict (will not be mutated).

    Returns:
        A copy of ``raw`` with ``version`` normalised to ``"1"``.

    Raises:
        ValueError: If ``version`` is not ``"1"``.
    """
    raw = dict(raw)  # do not mutate the input
    version = str(raw.get("version", "1"))
    match version:
        case "1":
            pass  # current canonical schema
        case _:
            raise ValueError(
                f"This config declares schema version '{version}', but this "
                f"strands-compose version only supports version '1'.\n"
                f"Upgrade: pip install --upgrade strands-compose"
            )
    raw["version"] = "1"
    return raw


def load(config: ConfigInput | list[ConfigInput]) -> ResolvedConfig:
    """Load config from file(s) or YAML string(s) and resolve to live objects.

    This is the main entry point for zero-code usage.
    Accepts a single source or a list of sources. Each source is either
    a file path (``str`` or ``Path``) or a raw YAML string. File paths
    are detected by checking if the path exists on disk; anything else
    is parsed as inline YAML.

    ### Pipeline:

    1. Parse each source (file read or inline YAML)
    2. Per-source: strip anchors, interpolate variables
    3. Sanitize collection keys (spaces/special chars -> underscores)
    4. Merge sources (if multiple), detect duplicate names
    5. Validate against schema (Pydantic)
    6. Resolve infrastructure (models, MCP, session — pure)
    7. Start MCP servers (so clients can connect)
    8. Create agents (Agent.__init__ auto-starts MCP clients)
    9. Wire orchestration / entry point

    Args:
        config: File path, raw YAML string, or list of either.

    Returns:
        ResolvedConfig with agents, entry (callable), and mcp_lifecycle.

    Raises:
        FileNotFoundError: Config file doesn't exist.
        ConfigurationError: Invalid YAML syntax, schema validation failure, or invalid references.

    ---
    ## REMARKS:

    When multiple sources are provided, collection sections (``agents``,
    ``models``, ``mcp_servers``, ``mcp_clients``, ``orchestrations``) are
    merged. Duplicate names within the same section raise ``ValueError``.
    Singleton fields (``entry``, ``session_manager``, ``log_level``) use
    last-wins semantics.

    **Side effect**: this function starts MCP servers during resolution.
    ``Agent.__init__`` auto-starts MCP clients (via ``process_tools()`` ->
    ``MCPClient.load_tools()``), and those clients need running servers to
    connect to. ``MCPLifecycle.start()`` is called **before** agent
    creation to satisfy this dependency.

    ``MCPLifecycle.start()`` is idempotent, so the caller's context
    manager (``async with resolved.mcp_lifecycle:``) is a no-op on enter
    but **still required for graceful shutdown** — ``__aexit__`` stops
    clients first, then servers.
    """
    app_config = load_config(config)

    logging.getLogger("strands_compose").setLevel(app_config.log_level.upper())

    infra = resolve_infra(app_config)

    # Start MCP servers BEFORE creating agents.
    # Initializing Agent starts MCP clients, so we need servers up first.
    infra.mcp_lifecycle.start()

    return load_session(app_config, infra)


def load_config(config: ConfigInput | list[ConfigInput]) -> AppConfig:
    """Parse and validate config from file(s) or YAML string(s).

    Accepts a single source or a list. Each source is auto-detected:

    - ``Path`` objects are always treated as file paths.
    - ``str`` values are treated as file paths if the file exists on disk;
      otherwise they are parsed as inline YAML content.

    When multiple sources are provided, their collection sections
    (``agents``, ``models``, ``mcp_servers``, ``mcp_clients``,
    ``orchestrations``) are merged. Duplicate names within the same
    section raise ``ValueError``. Singleton fields (``entry``,
    ``session_manager``, ``log_level``) use last-wins semantics.

    Each source's ``vars:`` block is applied only to that source
    (interpolation is per-source).

    Args:
        config: File path, raw YAML string, or list of either.

    Returns:
        Validated AppConfig instance.

    Raises:
        FileNotFoundError: A ``Path`` source doesn't exist.
        ConfigurationError: Invalid YAML, schema validation failure, or invalid references.
    """
    sources = config if isinstance(config, list) else [config]
    raw_configs = [parse_single_source(s) for s in sources]

    for raw in raw_configs:
        sanitize_collection_keys(raw)

    merged = merge_raw_configs(raw_configs) if len(raw_configs) > 1 else raw_configs[0]

    normalized = normalize(merged)
    try:
        app_config = AppConfig.model_validate(normalized)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        field_path = " -> ".join(str(loc) for loc in first_error["loc"])
        raise SchemaValidationError(
            f"Invalid config at '{field_path}': {first_error['msg']}\n"
            f"Check your YAML configuration file."
        ) from None
    validate_references(app_config)

    return app_config


def load_session(
    config: AppConfig,
    infra: ResolvedInfra,
    *,
    session_id: str | None = None,
) -> ResolvedConfig:
    """Create agents and orchestration from already-started infrastructure.

    This is the session-level counterpart to :func:`load`. Use it when
    you want to share MCP servers across multiple sessions (e.g. one
    session per HTTP request) while creating **isolated** agents per
    session.

    Typical server pattern::

        app_config = load_config("config.yaml")
        infra = resolve_infra(app_config)
        infra.mcp_lifecycle.start()

        # Per request:
        resolved = load_session(app_config, infra, session_id="abc")

    ``infra.mcp_lifecycle`` must already be started before calling this.

    Args:
        config: The validated AppConfig.
        infra: Resolved infrastructure with servers already started.
        session_id: Optional runtime session ID. When provided **and**
            the config declares a ``session_manager``, a fresh
            SessionManager is created with this ID so that each HTTP
            session gets its own isolated conversation state.

    Returns:
        ResolvedConfig with freshly created agents and entry point.
    """
    session_manager = infra.session_manager
    if session_id and config.session_manager is not None:
        session_manager = resolve_session_manager(
            config.session_manager,
            session_id_override=session_id,
        )

    # Agents used in Swarm orchestrations cannot have session_manager set.
    # Temporary until strands-agents supports swarm agents with session persistence.
    swarm_agent_names: set[str] = set()
    for orch in config.orchestrations.values():
        if isinstance(orch, SwarmOrchestrationDef):
            swarm_agent_names.update(orch.agents)

    agents = resolve_agents(
        agent_defs=config.agents,
        models=infra.models,
        mcp_clients=infra.clients,
        session_manager=session_manager,
        swarm_agent_names=swarm_agent_names,
    )
    orchestrators = resolve_orchestrations(
        config,
        agents,
        agent_defs=config.agents,
        models=infra.models,
        mcp_clients=infra.clients,
        session_manager=session_manager,
    )

    all_nodes = dict(agents) | orchestrators
    entry = all_nodes[config.entry]

    return ResolvedConfig(
        agents=agents,
        orchestrators=orchestrators,
        entry=entry,
        mcp_lifecycle=infra.mcp_lifecycle,
    )
