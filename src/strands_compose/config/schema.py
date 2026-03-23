"""Pydantic models for YAML configuration validation.

Pure data models — no runtime imports (Agent, MCPClient, etc.).
Validation catches user errors at parse time with clear messages.

Key Features:
    - Discriminated union for orchestration modes (delegate, swarm, graph)
    - Cross-section name collision detection via joint namespaces
    - Reference field descriptors for automated name sanitization
    - Inline and named model/hook/session_manager resolution
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator


class ModelDef(BaseModel):
    """LLM model configuration."""

    provider: str
    model_id: str
    params: dict[str, Any] = Field(default_factory=dict)


class HookDef(BaseModel):
    """Hook provider reference.

    ``type`` must be a ``module.path:ClassName`` import path or a
    ``./file.py:ClassName`` file-based import path.  The resolver raises
    ``ValueError`` if there is no colon separator.  ``params`` are forwarded
    as constructor kwargs.
    """

    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class ConversationManagerDef(BaseModel):
    """Conversation manager configuration.

    ``type`` must be a ``module.path:ClassName`` import path or a
    ``./file.py:ClassName`` file-based import path.  The resolver raises
    ``ValueError`` if there is no colon separator.  ``params`` are forwarded
    as constructor kwargs.

    Built-in strands classes:

    - ``strands.agent:SlidingWindowConversationManager``
    - ``strands.agent:SummarizingConversationManager``
    - ``strands.agent:NullConversationManager``
    """

    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class SessionManagerDef(BaseModel):
    """Session manager configuration.

    Built-in providers: ``"file"``, ``"s3"``, ``"agentcore"``.

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


class MCPServerDef(BaseModel):
    """MCP server definition."""

    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class MCPClientDef(BaseModel):
    """MCP client connection definition.

    Exactly one of ``server``, ``url``, or ``command`` must be set.

    ``params`` are forwarded to strands MCPClient (e.g., startup_timeout,
    tool_filters, prefix). ``transport_options`` are forwarded to the
    transport factory (e.g., headers, auth, timeout, http_client).
    """

    server: str | None = None
    url: str | None = None
    command: list[str] | None = None
    transport: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    transport_options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _exactly_one_connection_mode(self) -> MCPClientDef:
        """Validate that exactly one of server/url/command is set."""
        modes = [self.server is not None, self.url is not None, self.command is not None]
        count = sum(modes)
        if count == 0:
            raise ValueError(
                "MCPClientDef requires exactly one of 'server', 'url', or 'command'; got none."
            )
        if count > 1:
            raise ValueError(
                "MCPClientDef requires exactly one of 'server', 'url', or 'command'; got multiple."
            )
        return self


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
    """

    type: str | None = None
    """Custom agent factory import path.

    Format: ``module.path:ClassName`` or ``./file.py:ClassName``.
    When set, the factory is called instead of ``strands.Agent()`` directly.
    The ``agent_kwargs`` dict is spread as ``**kwargs`` to this factory.
    """
    agent_kwargs: dict[str, Any] = Field(default_factory=dict)
    """Additional keyword arguments passed to strands.Agent() or custom factory.

    Valid Agent parameters: messages, callback_handler,
    record_direct_tool_call, trace_attributes, state, plugins,
    structured_output_prompt, structured_output_model, tool_executor,
    retry_strategy, concurrent_invocation_mode, load_tools_from_directory.

    Warning: Use at your own risk — no schema-level validation is performed.
    Agent.__init__ has 24 explicit parameters and no **kwargs; any invalid
    key will raise TypeError at construction time.
    """
    model: str | ModelDef | None = None
    system_prompt: str | None = None
    description: str | None = None
    tools: list[str] = Field(default_factory=list)
    hooks: list[HookDef | str] = Field(default_factory=list)
    mcp: list[str] = Field(default_factory=list)
    tool_labels: dict[str, str] = Field(default_factory=dict)
    conversation_manager: ConversationManagerDef | None = None
    session_manager: SessionManagerDef | None = None


# --- Orchestration Models --- #


class DelegateConnectionDef(BaseModel):
    """A delegation connection: orchestrator calls agent as a tool."""

    agent: str
    description: str


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
    """Merged over the entry agent's ``agent_kwargs`` (orchestration wins).

    Common uses: ``system_prompt``, ``callback_handler``, ``conversation_manager``.
    """

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
COLLECTION_KEYS = ("models", "mcp_servers", "mcp_clients", "agents", "orchestrations")

# Groups of sections that share a lookup namespace — names must be unique within each group.
# mcp_servers / mcp_clients are independent namespaces and intentionally excluded.
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
    mcp_servers: dict[str, MCPServerDef] = Field(default_factory=dict)
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
                            f"Names must be unique within each section."
                        )
        return self
