"""Resolve SessionManagerDef -> strands SessionManager instance."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ...utils import load_object
from ..schema import SNAPSHOT_SESSION_PROVIDERS

if TYPE_CHECKING:
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager,
    )
    from strands.session.session_manager import SessionManager
    from strands.storage import Storage

    from ..schema import SessionManagerDef

# SnapshotSessionManager arguments a snapshot provider takes from ``params``.
# The other params are the session id and the storage settings read by resolve_snapshot_storage.
_SNAPSHOT_MANAGER_PARAMS = ("save_latest_on", "multi_agent_save_latest_on")


def _resolve_bedrock_agentcore_session_manager(
    params: dict[str, Any], session_id: str
) -> AgentCoreMemorySessionManager:
    """Resolve an AgentCoreMemorySessionManager from ``agentcore`` provider params.

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


def resolve_snapshot_storage(session_def: SessionManagerDef) -> Storage | None:
    """Build the storage backend of a snapshot provider.

    ``file-snapshot`` -> ``LocalFileStorage(storage_dir)`` (strands' default folder when
    ``storage_dir`` is omitted). ``s3-snapshot`` -> ``S3Storage(bucket, prefix=, region_name=)``.
    Every other provider, and any custom ``type``, owns its storage and returns ``None``.

    Building either storage has no side effects: no folder is created and no S3 client is
    opened until the first read or write.

    Args:
        session_def: Session definition from YAML; the schema has already checked its params.

    Returns:
        A new ``Storage`` instance, or ``None``.
    """
    if session_def.type is not None:
        return None
    provider = session_def.provider.lower()
    params = session_def.params
    if provider == "file-snapshot":
        from strands.storage import LocalFileStorage

        storage_dir = params.get("storage_dir")
        return LocalFileStorage(storage_dir) if storage_dir is not None else LocalFileStorage()
    if provider == "s3-snapshot":
        from strands.storage import S3Storage

        return S3Storage(
            params["bucket"],
            prefix=params.get("prefix") or "",
            region_name=params.get("region_name"),
        )
    return None


def resolve_session_manager(
    session_def: SessionManagerDef,
    *,
    session_id_override: str | None = None,
    storage: Storage | None = None,
) -> SessionManager:
    """Resolve a SessionManagerDef to a strands SessionManager.

    Built-in providers:

    - ``"file"`` -> ``strands.session.FileSessionManager``
    - ``"s3"`` -> ``strands.session.S3SessionManager``
    - ``"agentcore"`` -> ``AgentCoreMemorySessionManager``
    - ``"file-snapshot"`` -> ``strands.session.SnapshotSessionManager`` on ``LocalFileStorage``
    - ``"s3-snapshot"`` -> ``strands.session.SnapshotSessionManager`` on ``S3Storage``

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
        storage: Storage for a snapshot provider, shared with the agent by
            ``build_agent_from_def``. Built from ``params`` when ``None``. The other
            providers own their storage and ignore it.

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

    if provider in SNAPSHOT_SESSION_PROVIDERS:
        from strands.session import SnapshotSessionManager

        manager_params = {k: v for k, v in params.items() if k in _SNAPSHOT_MANAGER_PARAMS}
        return SnapshotSessionManager(
            session_id,
            storage=storage if storage is not None else resolve_snapshot_storage(session_def),
            **manager_params,
        )

    raise ValueError(
        f"Unknown session provider '{provider}'.\n"
        "Supported: 'file', 's3', 'agentcore', 'file-snapshot', 's3-snapshot'."
    )


def select_session_manager_def(
    *,
    leaf_def: SessionManagerDef | None,
    leaf_is_set: bool,
    global_def: SessionManagerDef | None,
) -> SessionManagerDef | None:
    """Pick the session manager def that applies to one leaf (agent or orchestration).

    Precedence (top wins): the leaf's own def, an explicit opt-out
    (``session_manager: ~``), the global def, none.

    Args:
        leaf_def: The leaf model's ``session_manager`` value.
        leaf_is_set: ``"session_manager" in leaf_model.model_fields_set``.
        global_def: The global ``AppConfig.session_manager`` def.

    Returns:
        The def to resolve, or ``None`` when the leaf has no session manager.
    """
    if leaf_def is not None:
        return leaf_def
    if leaf_is_set:
        return None
    return global_def


def resolve_leaf_session_manager(
    *,
    leaf_def: SessionManagerDef | None,
    leaf_is_set: bool,
    global_def: SessionManagerDef | None,
    session_id: str | None,
) -> SessionManager | None:
    """Apply the uniform leaf chain to one Pydantic model's ``session_manager`` field.

    The def is picked by :func:`select_session_manager_def` (leaf, explicit opt-out,
    global, none) and resolved with ``session_id`` as the override. A snapshot provider
    builds its storage from its params.

    Args:
        leaf_def: The leaf model's ``session_manager`` value.
        leaf_is_set: ``"session_manager" in leaf_model.model_fields_set``.
        global_def: The global ``AppConfig.session_manager`` def.
        session_id: Effective session id from ``load``.

    Returns:
        A new ``SessionManager`` instance or ``None``.
    """
    session_def = select_session_manager_def(
        leaf_def=leaf_def, leaf_is_set=leaf_is_set, global_def=global_def
    )
    if session_def is None:
        return None
    return resolve_session_manager(session_def, session_id_override=session_id)
