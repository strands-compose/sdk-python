"""strands-compose — Zero-code YAML-driven agent orchestration over strands-agents."""

from __future__ import annotations

from .config import (
    AppConfig,
    ConfigInput,
    ResolvedConfig,
    load,
    load_config,
)
from .config.resolvers.orchestrations import OrchestrationBuilder
from .exceptions import (
    CircularDependencyError,
    ConfigurationError,
    ImportResolutionError,
    SchemaValidationError,
    UnresolvedReferenceError,
)
from .hooks import EventPublisher, MaxToolCallsGuard, StopGuard, ToolNameSanitizer
from .mcp import create_mcp_client
from .renderers import AnsiRenderer
from .tools import (
    multiagent_as_tool,
    serialize_multiagent_result,
)
from .types import EventType, StreamEvent
from .utils import cli_errors
from .wire import EventQueue, make_event_queue

__all__ = [
    "AnsiRenderer",
    "AppConfig",
    "CircularDependencyError",
    "ConfigInput",
    "ConfigurationError",
    "EventPublisher",
    "EventQueue",
    "EventType",
    "ImportResolutionError",
    "MaxToolCallsGuard",
    "OrchestrationBuilder",
    "ResolvedConfig",
    "SchemaValidationError",
    "StopGuard",
    "StreamEvent",
    "ToolNameSanitizer",
    "UnresolvedReferenceError",
    "cli_errors",
    "create_mcp_client",
    "load",
    "load_config",
    "make_event_queue",
    "multiagent_as_tool",
    "serialize_multiagent_result",
]
