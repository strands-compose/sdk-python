"""Shared exception types for strands-compose configuration errors."""

from __future__ import annotations


class ConfigurationError(ValueError):
    """Raised when a strands-compose configuration is invalid.

    Subclasses ``ValueError`` so callers that catch ``ValueError`` still work,
    but allows more specific ``except ConfigurationError`` handling.
    """


class SchemaValidationError(ConfigurationError):
    """Raised when YAML config fails Pydantic schema validation."""


class UnresolvedReferenceError(ConfigurationError):
    """Raised when a config references a non-existent model, agent, or MCP resource."""


class CircularDependencyError(ConfigurationError):
    """Raised when orchestration definitions contain a dependency cycle."""


class ImportResolutionError(ConfigurationError):
    """Raised when a custom import spec (``module.path:Name``) cannot be loaded."""
