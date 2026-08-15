"""YAML configuration loading, validation, and resolution."""

from __future__ import annotations

from .interpolation import interpolate, strip_anchors
from .loaders import ConfigInput, load, load_config
from .resolvers import ResolvedConfig
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
    ModelDef,
    OrchestrationDef,
    PluginDef,
    SessionManagerDef,
    SwarmOrchestrationDef,
)

__all__ = [
    "COLLECTION_KEYS",
    "JOINT_NAMESPACES",
    "AgentDef",
    "AppConfig",
    "ConfigInput",
    "ConversationManagerDef",
    "DelegateConnectionDef",
    "DelegateOrchestrationDef",
    "GraphEdgeDef",
    "GraphOrchestrationDef",
    "HookDef",
    "MCPClientDef",
    "ModelDef",
    "OrchestrationDef",
    "PluginDef",
    "ResolvedConfig",
    "SessionManagerDef",
    "SwarmOrchestrationDef",
    "interpolate",
    "load",
    "load_config",
    "strip_anchors",
]
