"""Pydantic models for YAML configuration validation.

Pure data models — no runtime imports (Agent, MCPClient, etc.).
Validation catches user errors at parse time with clear messages.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    ValidationError,
    model_validator,
)


class CacheDef(BaseModel):
    """Prompt caching settings, mirroring strands' ``CacheConfig`` fields.

    Only the keys written in YAML are passed on, so strands keeps its own defaults.
    """

    model_config = ConfigDict(extra="forbid")

    strategy: Literal["auto", "anthropic"] = "auto"
    ttl: str | None = None
    system_prompt_ttl: StrictBool | str = True
    cache_key: str | Literal[False] | None = None
    tools_ttl: StrictBool | str | None = None


class ModelDef(BaseModel):
    """LLM model configuration."""

    provider: str
    model_id: str
    cache: CacheDef | StrictBool | None = None
    """Prompt caching, off when absent or ``false``.

    ``true`` enables strands' automatic caching (``CacheConfig(strategy="auto")``);
    a mapping sets ``CacheConfig`` fields (see :class:`CacheDef`). Unknown keys are
    rejected at parse time. Providers apply only the fields they support.
    """
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _cache_set_once(self) -> ModelDef:
        """Reject ``params.cache_config``: caching is configured through ``cache``."""
        if "cache_config" in self.params:
            raise ValueError(
                "params.cache_config is not supported; set caching on the model instead, "
                "e.g. 'cache: true' or 'cache: {strategy: auto, ttl: 1h}'."
            )
        return self


class HookDef(BaseModel):
    """Hook provider reference.

    ``type`` must be a ``module.path:ClassName`` import path or a
    ``./file.py:ClassName`` file-based import path.  A malformed spec raises
    ``ImportResolutionError``.  ``params`` are forwarded as constructor kwargs.
    """

    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class PluginDef(BaseModel):
    """Agent plugin reference.

    ``type`` must be a ``module.path:ClassName`` import path or a
    ``./file.py:ClassName`` file-based import path, resolving to a ``Plugin``
    subclass or a factory returning one.  ``params`` are forwarded as
    constructor (or factory) kwargs.  See ``docs/configuration/Chapter_19.md``.
    """

    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class ConversationManagerDef(BaseModel):
    """Conversation manager configuration.

    ``type`` must be a ``module.path:ClassName`` import path or a
    ``./file.py:ClassName`` file-based import path.  A malformed spec raises
    ``ConfigurationError``.  ``params`` are forwarded as constructor kwargs.

    Built-in strands classes:

    - ``strands.agent:SlidingWindowConversationManager``
    - ``strands.agent:SummarizingConversationManager``
    - ``strands.agent:NullConversationManager``
    """

    type: str
    params: dict[str, Any] = Field(default_factory=dict)


_NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# ``params`` of the built-in snapshot session providers, which run on strands'
# SnapshotSessionManager: the storage fields first, then the manager arguments. The
# defaults are strands' own and are never passed on. ``save_latest_on: trigger`` is left
# out: compose exposes no public manager handle to call ``save_snapshot`` with, so nothing
# would ever be saved.


class FileSnapshotParamsDef(BaseModel):
    """``params`` of the ``file-snapshot`` provider, stored in strands' ``LocalFileStorage``."""

    model_config = ConfigDict(extra="forbid")

    storage_dir: _NonEmptyStr | None = None
    session_id: str | None = None
    save_latest_on: Literal["invocation", "message"] = "invocation"
    multi_agent_save_latest_on: Literal["node", "invocation"] = "node"


class S3SnapshotParamsDef(BaseModel):
    """``params`` of the ``s3-snapshot`` provider, stored in strands' ``S3Storage``."""

    model_config = ConfigDict(extra="forbid")

    bucket: _NonEmptyStr
    prefix: str | None = None
    region_name: str | None = None
    session_id: str | None = None
    save_latest_on: Literal["invocation", "message"] = "invocation"
    multi_agent_save_latest_on: Literal["node", "invocation"] = "node"


# Built-in session providers backed by strands' SnapshotSessionManager, each mapped to the
# model that checks its ``params``.
SNAPSHOT_SESSION_PROVIDERS: dict[str, type[BaseModel]] = {
    "file-snapshot": FileSnapshotParamsDef,
    "s3-snapshot": S3SnapshotParamsDef,
}


class SessionManagerDef(BaseModel):
    """Session manager configuration.

    Built-in providers: ``"file"``, ``"s3"``, ``"agentcore"``, and the snapshot
    providers ``"file-snapshot"`` and ``"s3-snapshot"`` (see
    :data:`SNAPSHOT_SESSION_PROVIDERS`). Snapshot provider ``params`` are checked
    by :class:`FileSnapshotParamsDef` and :class:`S3SnapshotParamsDef`.

    For a custom class, set ``type`` to an import path
    (``"module.path:ClassName"``).  The class must be a subclass of
    ``strands.session.SessionManager``.  When ``type`` is set, ``provider``
    is ignored.

    Session ID resolution order:
      1. Runtime override (e.g., HTTP session header)
      2. ``params.session_id``
      3. Random UUID (fresh session per CLI run)
    """

    provider: str = "file"
    type: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _snapshot_params_are_valid(self) -> SessionManagerDef:
        """Check ``params`` of a built-in snapshot provider against its params model.

        A custom ``type`` replaces ``provider``, so its params are left alone.
        """
        params_def = SNAPSHOT_SESSION_PROVIDERS.get(self.provider.lower())
        if self.type is not None or params_def is None:
            return self
        try:
            params_def.model_validate(self.params)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
            raise ValueError(
                f"session_manager provider '{self.provider}' has invalid params: {problems}"
            ) from None
        return self


class MCPClientDef(BaseModel):
    """MCP client connection definition.

    Exactly one of ``url`` or ``command`` must be set.

    ``params`` are forwarded to strands MCPClient (e.g., startup_timeout,
    tool_filters, prefix). ``transport_options`` are forwarded to the
    transport factory (e.g., headers, auth, timeout, http_client).
    """

    url: str | None = None
    command: list[str] | None = None
    transport: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    transport_options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _exactly_one_connection_mode(self) -> MCPClientDef:
        """Validate that exactly one of url/command is set."""
        count = sum([self.url is not None, self.command is not None])
        if count == 0:
            raise ValueError("MCPClientDef requires exactly one of 'url' or 'command'; got none.")
        if count > 1:
            raise ValueError("MCPClientDef requires exactly one of 'url' or 'command'; got both.")
        return self


# Agent keyword arguments that ``build_agent_from_def`` passes itself, so the same key in
# ``agent_kwargs`` is rejected at parse time (it would reach ``Agent()`` twice). Each one
# is set through the agent's key or its dedicated ``AgentDef`` field. Keep in sync with
# ``builder_kwargs`` in ``config/resolvers/agents.py``.
# ``load_tools_from_directory`` is only passed on the standard path (no custom ``type``),
# but is reserved everywhere to keep one rule.
RESERVED_AGENT_KWARGS = (
    "name",
    "agent_id",
    "model",
    "system_prompt",
    "description",
    "tools",
    "hooks",
    "plugins",
    "conversation_manager",
    "session_manager",
    "load_tools_from_directory",
)


def _reject_reserved_agent_kwargs(agent_kwargs: dict[str, Any], owner: str) -> None:
    """Raise if ``agent_kwargs`` contains a key strands-compose sets itself.

    Args:
        agent_kwargs: The ``agent_kwargs`` dict to check.
        owner: Where the dict lives, for the error message.

    Raises:
        ValueError: If any reserved key is present.
    """
    clashing = sorted(set(agent_kwargs) & set(RESERVED_AGENT_KWARGS))
    if clashing:
        raise ValueError(
            f"{owner}: agent_kwargs must not contain {clashing}; strands-compose sets these "
            f"itself. name and agent_id come from the agent's key, the others from the "
            f"matching agent fields.\n"
            f"Reserved: {sorted(RESERVED_AGENT_KWARGS)}"
        )


class AgentDef(BaseModel):
    """Top-level agent definition.

    All agents are defined flat under the ``agents:`` section.
    Multi-agent orchestration is configured separately in the ``orchestrations:`` section.

    ``tools`` accepts spec strings:

    - ``"module.path:function_name"`` — single function from module
    - ``"module.path"`` — all ``@tool`` functions in module
    - ``"./path/to/file.py:function_name"`` — single function from file
    - ``"./path/to/file.py"`` — all ``@tool`` functions in file
    - ``"./path/to/dir/"`` — all ``@tool`` functions in directory

    ``hooks`` accepts import-path strings (``"module.path:ClassName"`` or
    ``"./file.py:ClassName"``) or inline :class:`HookDef` objects with
    explicit type + optional params.

    ``plugins`` mirrors ``hooks``: import-path strings (``"module.path:ClassName"``
    or ``"./file.py:ClassName"``) or inline :class:`PluginDef` objects with
    explicit type + optional params.  See ``docs/configuration/Chapter_19.md``.
    """

    type: str | None = None
    """Custom agent factory import path.

    Format: ``module.path:ClassName`` or ``./file.py:ClassName``.
    When set, the factory is called instead of ``strands.Agent()`` directly.
    The ``agent_kwargs`` dict is spread as ``**kwargs`` to this factory.
    """
    agent_kwargs: dict[str, Any] = Field(default_factory=dict)
    """Additional keyword arguments passed to strands.Agent() or custom factory.

    Keys that strands-compose passes itself (:data:`RESERVED_AGENT_KWARGS`) are
    rejected at parse time. ``name`` and ``agent_id`` come from the agent's key; set the others as
    fields on the agent.

    Warning: Use at your own risk — the remaining keys are not validated.
    Agent.__init__ has no **kwargs; any invalid key will raise TypeError at
    construction time.
    """
    model: str | ModelDef | None = None
    system_prompt: str | None = None
    description: str | None = None
    tools: list[str] = Field(default_factory=list)
    hooks: list[HookDef | str] = Field(default_factory=list)
    plugins: list[PluginDef | str] = Field(default_factory=list)
    mcp: list[str] = Field(default_factory=list)
    conversation_manager: ConversationManagerDef | None = None
    session_manager: SessionManagerDef | None = None

    @model_validator(mode="after")
    def _agent_kwargs_avoid_reserved_keys(self) -> AgentDef:
        """Reject ``agent_kwargs`` keys that the agent builder already passes."""
        _reject_reserved_agent_kwargs(self.agent_kwargs, "agent")
        return self


# --- Orchestration Models --- #


class DelegateConnectionDef(BaseModel):
    """A delegation connection: orchestrator calls agent as a tool."""

    agent: str
    description: str
    preserve_context: bool = True
    """Whether the delegate keeps its history between calls.

    ``False`` resets the agent to its construction-time baseline every call.
    Rejected for a Swarm or Graph target (no baseline), and rejected by strands
    itself if the agent has a session manager.
    """


class DelegateOrchestrationDef(BaseModel):
    """Delegate mode: entry agent calls other agents as tools.

    A **new** Agent is constructed from the ``entry_name`` agent's blueprint
    (model, system_prompt, hooks, tools, etc.) with delegate tools added for
    each connection. The original agent is never mutated.

    Entry point is explicit via ``entry_name`` (consistent with swarm/graph).

    ``agent_kwargs`` is **merged** over the entry agent's ``agent_kwargs`` —
    orchestration values win on conflict, unset keys are inherited.
    """

    mode: Literal["delegate"] = "delegate"
    entry_name: str
    connections: list[DelegateConnectionDef]
    session_manager: SessionManagerDef | None = None
    hooks: list[HookDef | str] = Field(default_factory=list)
    agent_kwargs: dict[str, Any] = Field(default_factory=dict)
    """Extra ``Agent`` kwargs merged over the entry agent's ``agent_kwargs`` (orchestration wins).

    Keys in :data:`RESERVED_AGENT_KWARGS` are rejected; change those on the entry agent.
    """

    @model_validator(mode="after")
    def _agent_kwargs_avoid_reserved_keys(self) -> DelegateOrchestrationDef:
        """Reject ``agent_kwargs`` keys that the agent builder already passes."""
        _reject_reserved_agent_kwargs(self.agent_kwargs, "delegate orchestration")
        return self

    @classmethod
    def reference_fields(cls) -> dict[str, str]:
        """Return mapping of JSON paths to reference types for name sanitization."""
        return {
            "entry_name": "node",
            "connections[].agent": "node",
        }


class SwarmOrchestrationDef(BaseModel):
    """Swarm mode: collaborative handoffs between peer agents.

    Agents transfer control to each other via handoff_to_agent tool.
    Uses strands Swarm under the hood.
    """

    mode: Literal["swarm"] = "swarm"
    agents: list[str]
    entry_name: str
    max_handoffs: int = 20
    max_iterations: int = 20
    execution_timeout: float = 900.0
    node_timeout: float = 300.0
    session_manager: SessionManagerDef | None = None
    hooks: list[HookDef | str] = Field(default_factory=list)

    @classmethod
    def reference_fields(cls) -> dict[str, str]:
        """Return mapping of JSON paths to reference types for name sanitization."""
        return {
            "entry_name": "node",
            "agents[]": "node",
        }


class GraphEdgeDef(BaseModel):
    """An edge in a graph orchestration."""

    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")
    condition: str | None = None
    model_config = {"populate_by_name": True}


class GraphOrchestrationDef(BaseModel):
    """Graph mode: DAG-based orchestration with conditional edges.

    Agents execute in parallel batches based on dependency order.
    Uses strands Graph under the hood.
    """

    mode: Literal["graph"] = "graph"
    edges: list[GraphEdgeDef]
    max_node_executions: int | None = None
    execution_timeout: float | None = None
    node_timeout: float | None = None
    reset_on_revisit: bool = False
    session_manager: SessionManagerDef | None = None
    entry_name: str
    hooks: list[HookDef | str] = Field(default_factory=list)

    @classmethod
    def reference_fields(cls) -> dict[str, str]:
        """Return mapping of JSON paths to reference types for name sanitization."""
        return {
            "entry_name": "node",
            "edges[].from": "node",
            "edges[].to": "node",
        }


OrchestrationDef = Annotated[
    DelegateOrchestrationDef | SwarmOrchestrationDef | GraphOrchestrationDef,
    Field(discriminator="mode"),
]


# Sections that hold named dict collections (merged across config sources).
# IMPORTANT: these must exactly match the dict field names on AppConfig below.
COLLECTION_KEYS = ("models", "mcp_clients", "agents", "orchestrations")

# Groups of sections that share a lookup namespace — names must be unique within each group.
# mcp_clients is an independent namespace and intentionally excluded.
JOINT_NAMESPACES: tuple[tuple[str, ...], ...] = (("agents", "orchestrations"),)


class AppConfig(BaseModel):
    """Root YAML configuration.

    Orchestrations are defined as a dict of named orchestration blocks
    that can reference each other for arbitrary nesting.
    """

    # IF YOU ADD A NEW SECTION, UPDATE:
    # 1. COLLECTION_KEYS above (if it's a named dict collection)
    # 2. JOINT_NAMESPACES above (if it shares a namespace with another section)

    version: str = "1"
    """Schema version — omit to use the default ``"1"``."""
    models: dict[str, ModelDef] = Field(default_factory=dict)
    mcp_clients: dict[str, MCPClientDef] = Field(default_factory=dict)
    agents: dict[str, AgentDef] = Field(default_factory=dict)
    session_manager: SessionManagerDef | None = None
    orchestrations: dict[str, OrchestrationDef] = Field(default_factory=dict)
    entry: str
    log_level: str = "WARNING"

    @model_validator(mode="after")
    def _validate_entry_ref(self) -> AppConfig:
        """Ensure entry references a defined agent or orchestration."""
        valid_names = set(self.agents) | set(self.orchestrations)
        if self.entry not in valid_names:
            raise ValueError(
                f"entry '{self.entry}' is not defined under agents: or orchestrations:.\n"
                f"Available: {', '.join(sorted(valid_names)) or '(none)'}"
            )
        return self

    @model_validator(mode="after")
    def _validate_no_name_collisions(self) -> AppConfig:
        """Ensure no name collisions within shared namespaces (see :data:`JOINT_NAMESPACES`)."""
        for namespace in JOINT_NAMESPACES:
            entries = [(key, set(getattr(self, key))) for key in namespace]
            for i, (section_a, names_a) in enumerate(entries):
                for section_b, names_b in entries[i + 1 :]:
                    overlap = names_a & names_b
                    if overlap:
                        raise ValueError(
                            f"Name collision between {section_a} and {section_b}: "
                            f"{sorted(overlap)}.\n"
                            f"Names must be unique across {' and '.join(namespace)} — "
                            f"they share one lookup namespace."
                        )
        return self
