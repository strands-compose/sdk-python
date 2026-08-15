"""Public loading functions — parse YAML config and resolve to live objects.

Usage::

    from strands_compose import load

    # Single file
    resolved = load("config.yaml")

    # Multiple files (merged)
    resolved = load(["agents.yaml", "mcp.yaml"])

    # Raw YAML string
    resolved = load("agents:\\n  a:\\n    system_prompt: hi")

    result = resolved.entry("Hello!")

A server parses once and resolves per session::

    app_config = load_config("config.yaml")
    resolved = load(app_config, session_id="abc")
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ...exceptions import SchemaValidationError
from ..resolvers import (
    ResolvedConfig,
    resolve_agents,
    resolve_mcp_client,
    resolve_model,
    resolve_orchestrations,
)
from ..schema import (
    AppConfig,
    GraphOrchestrationDef,
    SessionManagerDef,
    SwarmOrchestrationDef,
)
from .helpers import merge_raw_configs, parse_single_source, sanitize_collection_keys
from .validators import validate_references

if TYPE_CHECKING:
    from strands.models import Model
    from strands.tools.mcp import MCPClient as StrandsMCPClient

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
    if version != "1":
        raise ValueError(
            f"This config declares schema version '{version}', but this "
            f"strands-compose version only supports version '1'.\n"
            f"Upgrade: pip install --upgrade strands-compose"
        )
    raw["version"] = "1"
    return raw


def load(
    config: ConfigInput | list[ConfigInput] | AppConfig,
    *,
    session_id: str | None = None,
) -> ResolvedConfig:
    """Load config and resolve it to live strands objects.

    Pass a file path, a raw YAML string, a list of either, or an
    already-validated :class:`AppConfig`.  File paths are detected by checking
    if the path exists on disk; anything else is parsed as inline YAML.

    Every call builds **fresh** agents and MCP clients, so each call is an
    isolated session — N sessions against a ``command:`` client means N stdio
    subprocesses.  A long-running server parses once with :func:`load_config`
    and then calls this per session with the ``AppConfig`` and a ``session_id``.

    ### Pipeline:

    1. Parse each source (file read or inline YAML) — skipped for an ``AppConfig``
    2. Per-source: strip anchors, interpolate variables
    3. Sanitize collection keys (spaces/special chars -> underscores)
    4. Merge sources (if multiple), detect duplicate names
    5. Validate against schema (Pydantic) and check cross-references
    6. Resolve models and MCP clients
    7. Create agents, wire orchestrations, pick the entry point

    Args:
        config: File path, raw YAML string, list of either, or a validated
            ``AppConfig``.
        session_id: Optional session ID.  Combined with
            ``session_manager.params.session_id`` (if any) and a
            ``uuid.uuid4()`` fallback to derive a single effective session ID
            that is threaded into every per-agent and per-orchestration
            session-manager resolution.  When ``None`` and no global
            ``session_manager:`` is configured, leaves fall back to their own
            UUIDs per ``resolve_session_manager``.

    Returns:
        ResolvedConfig with agents, orchestrators, and entry (callable).

    Raises:
        FileNotFoundError: Config file doesn't exist.
        ConfigurationError: Invalid YAML syntax, schema validation failure, or
            invalid references.
        ValueError: The global ``session_manager`` uses the ``agentcore``
            provider, which requires a unique ``actor_id`` per agent.
    """

    if isinstance(config, AppConfig):
        app_config = config
    else:
        app_config = load_config(config)
        # Apply the configured level only when this call parsed the config
        logging.getLogger("strands_compose").setLevel(app_config.log_level.upper())

    _reject_global_agentcore_session_manager(app_config.session_manager)

    models: dict[str, Model] = {}
    for name, model_def in app_config.models.items():
        models[name] = resolve_model(model_def)
        logger.info("model=<%s>, provider=<%s> | resolved model", name, model_def.provider)

    clients: dict[str, StrandsMCPClient] = {}
    for name, client_def in app_config.mcp_clients.items():
        clients[name] = resolve_mcp_client(client_def)
        logger.info("client=<%s> | resolved MCP client", name)

    effective_session_id = _effective_session_id(app_config, session_id)

    agents = resolve_agents(
        agent_defs=app_config.agents,
        models=models,
        mcp_clients=clients,
        global_session_manager_def=app_config.session_manager,
        session_id=effective_session_id,
        orchestration_agent_names=_orchestration_agent_names(app_config),
    )
    orchestrators = resolve_orchestrations(
        app_config,
        agents,
        agent_defs=app_config.agents,
        models=models,
        mcp_clients=clients,
        global_session_manager_def=app_config.session_manager,
        session_id=effective_session_id,
    )

    entry = (dict(agents) | orchestrators)[app_config.entry]

    return ResolvedConfig(agents=agents, orchestrators=orchestrators, entry=entry)


def load_config(config: ConfigInput | list[ConfigInput]) -> AppConfig:
    """Parse and validate config from file(s) or YAML string(s).

    Accepts a single source or a list. Each source is auto-detected:

    - ``Path`` objects are always treated as file paths.
    - ``str`` values are treated as file paths if the file exists on disk;
      otherwise they are parsed as inline YAML content.

    When multiple sources are provided, their collection sections
    (``agents``, ``models``, ``mcp_clients``, ``orchestrations``) are
    merged. Duplicate names within the same section raise ``ValueError``.
    Singleton fields (``entry``, ``session_manager``, ``log_level``) use
    last-wins semantics.

    Each source's ``vars:`` block is applied only to that source
    (interpolation is per-source).

    Use this when you want to parse and validate once — at process startup,
    or in CI — and hand the result to :func:`load` one or more times.

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


def _reject_global_agentcore_session_manager(session_manager: SessionManagerDef | None) -> None:
    """Reject the ``agentcore`` session provider when set globally.

    ``agentcore`` requires a unique ``actor_id`` per agent, so a single global
    definition cannot be shared. Fail fast rather than silently giving every
    agent the same actor.

    Args:
        session_manager: The global ``AppConfig.session_manager`` def.

    Raises:
        ValueError: If the global provider is ``agentcore``.
    """
    if session_manager is not None and session_manager.provider.lower() == "agentcore":
        raise ValueError(
            "The 'agentcore' session manager cannot be set globally.\n"
            "Configure it per-agent — 'actor_id' must be unique per agent."
        )


def _effective_session_id(config: AppConfig, session_id: str | None) -> str | None:
    """Derive the one session ID shared by every leaf that falls back to the global def.

    Precedence: the caller's ``session_id`` -> ``session_manager.params.session_id``
    -> a fresh UUID. Returns ``None`` when no global ``session_manager:`` is
    configured, letting each leaf generate its own ID.

    Args:
        config: The validated AppConfig.
        session_id: The caller-supplied session ID, if any.

    Returns:
        The effective session ID, or ``None``.
    """
    if session_id is not None:
        return session_id
    if config.session_manager is None:
        return None
    yaml_session_id = (config.session_manager.params or {}).get("session_id")
    return yaml_session_id or str(uuid.uuid4())


def _orchestration_agent_names(config: AppConfig) -> set[str]:
    """Collect the agents used as nodes in a Swarm or Graph orchestration.

    Those agents cannot carry a session manager — a strands-agents limitation
    that ``resolve_agents`` reports as a config error.

    Args:
        config: The validated AppConfig.

    Returns:
        Names of every agent referenced by a swarm or graph orchestration.
    """
    names: set[str] = set()
    for orch in config.orchestrations.values():
        if isinstance(orch, SwarmOrchestrationDef):
            names.update(orch.agents)
        elif isinstance(orch, GraphOrchestrationDef):
            names.add(orch.entry_name)
            for edge in orch.edges:
                names.add(edge.from_agent)
                names.add(edge.to_agent)
    return names
