"""Resolve SessionManagerDef -> strands SessionManager instance."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ...utils import load_object

if TYPE_CHECKING:
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager,
    )
    from strands.session.session_manager import SessionManager

    from ..schema import SessionManagerDef


def _resolve_bedrock_agentcore_session_manager(
    params: dict[str, Any], session_id: str
) -> AgentCoreMemorySessionManager:
    """Helper to resolve an AgentCoreMemorySessionManager with Bedrock-specific config.

    This is used by resolve_session_manager when the provider is "agentcore".
    It extracts the relevant parameters from the config and constructs the
    necessary AgentCoreMemoryConfig and AgentCoreMemorySessionManager objects.

    Args:
        params: The "params" dict from the SessionManagerDef for an "agentcore" provider.
        session_id: The resolved session ID to use for the session manager.

    Returns:
        An instance of AgentCoreMemorySessionManager configured with the provided parameters.

    Raises:
        ImportError: If ``bedrock_agentcore`` is not installed.
        ValueError: If ``actor_id`` is missing from ``params``.
    """
    try:
        from bedrock_agentcore.memory.integrations.strands.config import (
            AgentCoreMemoryConfig as ACMConfig,
        )
        from bedrock_agentcore.memory.integrations.strands.session_manager import (
            AgentCoreMemorySessionManager as ACMManager,
        )
    except ImportError:
        raise ImportError(
            "The 'agentcore' session manager requires the agentcore-memory extra:\n"
            "  pip install strands-compose[agentcore-memory]"
        ) from None

    config_fields = {
        "memory_id",
        "actor_id",
        "retrieval_config",
        "batch_size",
        "flush_interval_seconds",
        "context_tag",
        "filter_restored_tool_context",
    }
    # Require "actor_id" in params. Recommended to use agent name for clarity.
    # Agent resolver prevents duplicated agent names, so this ensures uniqueness.
    if "actor_id" not in params:
        raise ValueError(
            "The 'agentcore' session manager requires unique 'actor_id' in params.\n"
            "Recommended to use your agent name."
        )
    # Split params: AgentCoreMemoryConfig fields vs constructor kwargs.
    # Extract session_id from params to avoid duplicate keyword argument
    config_params = {k: v for k, v in params.items() if k in config_fields and k != "session_id"}
    constructor_params = {k: v for k, v in params.items() if k not in config_fields}
    config = ACMConfig(session_id=session_id, **config_params)
    return ACMManager(config, **constructor_params)


def resolve_session_manager(
    session_def: SessionManagerDef,
    *,
    session_id_override: str | None = None,
) -> SessionManager:
    """Resolve a SessionManagerDef to a strands SessionManager.

    Built-in providers:

    - ``"file"`` -> ``strands.session.FileSessionManager``
    - ``"s3"`` -> ``strands.session.S3SessionManager``
    - ``"agentcore"`` -> ``AgentCoreMemorySessionManager``

    Custom class: set ``type`` to an import path (``"mod:Class"``).  The
    class must be a subclass of ``strands.session.SessionManager`` and will
    be instantiated as ``cls(session_id=<id>, **params)``.  When ``type``
    is set, ``provider`` is ignored.

    Session ID resolution (in order):

    1. ``session_id_override`` (HTTP server runtime session ID)
    2. ``params.session_id`` (from YAML config)
    3. Random UUID (CLI mode — fresh session per run)

    Args:
        session_def: Session definition from YAML.
        session_id_override: When provided, overrides the session ID.
            Used by the server to give each HTTP session its own
            isolated session manager.

    Returns:
        Configured SessionManager instance.

    Raises:
        ValueError: If the provider is unknown.
        TypeError: If a custom ``type`` class is not a SessionManager subclass.
    """
    from strands.session.session_manager import SessionManager as _SessionManager

    # Session ID resolution: override > params > random UUID
    session_id = session_id_override or session_def.params.get("session_id") or str(uuid.uuid4())

    # Extract session_id from params to avoid duplicate keyword argument
    params = {k: v for k, v in session_def.params.items() if k != "session_id"}

    # Custom class takes precedence over built-in provider names
    if session_def.type is not None:
        cls = load_object(session_def.type, target="session manager")
        instance = cls(session_id=session_id, **params)
        if not isinstance(instance, _SessionManager):
            raise TypeError(
                f"Custom session manager '{session_def.type}' must be a subclass of "
                f"strands.session.SessionManager, got {type(instance).__name__}."
            )
        return instance

    provider = session_def.provider.lower()

    if provider == "file":
        from strands.session import FileSessionManager

        return FileSessionManager(session_id=session_id, **params)

    if provider == "s3":
        from strands.session import S3SessionManager

        return S3SessionManager(session_id=session_id, **params)

    if provider == "agentcore":
        return _resolve_bedrock_agentcore_session_manager(params, session_id)

    raise ValueError(
        f"Unknown session provider '{provider}'.\nSupported: 'file', 's3', 'agentcore'."
    )
