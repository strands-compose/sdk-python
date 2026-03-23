"""YAML configuration loading, validation, and resolution."""

from __future__ import annotations

from .interpolation import interpolate, strip_anchors
from .loaders import ConfigInput, load, load_config, load_session
from .resolvers import ResolvedConfig, ResolvedInfra, resolve_infra
from .schema import (
    COLLECTION_KEYS,
    JOINT_NAMESPACES,
    AgentDef,
    AppConfig,
    ConversationManagerDef,
    DelegateConnectionDef,
    DelegateOrchestrationDef,
    GraphEdgeDef,
    GraphOrchestrationDef,
    HookDef,
    MCPClientDef,
    MCPServerDef,
    ModelDef,
    OrchestrationDef,
    SessionManagerDef,
    SwarmOrchestrationDef,
)

__all__ = [
    "AgentDef",
    "AppConfig",
    "COLLECTION_KEYS",
    "ConversationManagerDef",
    "JOINT_NAMESPACES",
    "ConfigInput",
    "DelegateConnectionDef",
    "DelegateOrchestrationDef",
    "GraphEdgeDef",
    "GraphOrchestrationDef",
    "HookDef",
    "MCPClientDef",
    "MCPServerDef",
    "ModelDef",
    "OrchestrationDef",
    "SessionManagerDef",
    "SwarmOrchestrationDef",
    "ResolvedConfig",
    "ResolvedInfra",
    "interpolate",
    "load",
    "load_config",
    "load_session",
    "resolve_infra",
    "strip_anchors",
]
