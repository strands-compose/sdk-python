"""Internal helpers — parsing, sanitizing, and merging raw YAML dicts."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import yaml

from ...exceptions import ConfigurationError
from ..interpolation import interpolate, strip_anchors
from ..schema import (
    COLLECTION_KEYS,
    DelegateOrchestrationDef,
    GraphOrchestrationDef,
    SwarmOrchestrationDef,
)

logger = logging.getLogger(__name__)

# Valid config name: alphanumeric, underscores, hyphens, max 64 chars.
_VALID_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def sanitize_name(name: str) -> str:
    """Sanitize a config key to ``[a-zA-Z0-9_\\-]{1,64}``."""
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = sanitized.strip("_")
    if len(sanitized) > 64:
        logger.warning(
            "name=<%s>, truncated=<%s> | name truncated to 64 characters",
            name,
            sanitized[:64],
        )
        sanitized = sanitized[:64]
    return sanitized


def sanitize_collection_keys(raw: dict) -> None:
    """Sanitize dictionary keys in all collection sections (in place)."""
    rename_map: dict[str, str] = {}

    for section_key in COLLECTION_KEYS:
        section = raw.get(section_key)
        if not isinstance(section, dict):
            continue

        new_section: dict = {}
        for original_name, definition in section.items():
            sanitized = (
                sanitize_name(original_name)
                if not _VALID_NAME_RE.match(original_name)
                else original_name
            )

            if not sanitized:
                raise ValueError(
                    f"Name '{original_name}' in '{section_key}' is empty after sanitization."
                )
            if sanitized in new_section:
                raise ValueError(
                    f"Duplicate name in '{section_key}' after sanitization: "
                    f"'{original_name}' -> '{sanitized}' collides with an "
                    f"existing entry."
                )

            if sanitized == original_name:
                new_section[original_name] = definition
                continue

            logger.warning(
                "section=<%s>, original=<%s>, sanitized=<%s> | sanitized collection key",
                section_key,
                original_name,
                sanitized,
            )
            rename_map[original_name] = sanitized
            new_section[sanitized] = definition

        raw[section_key] = new_section

    if rename_map:
        update_references(raw, rename_map)


def update_references(raw: dict, rename_map: dict[str, str]) -> None:
    """Update internal name references after key sanitization."""

    def _rename(name: str) -> str:
        return rename_map.get(name, name)

    # 1. Entry reference
    if isinstance(raw.get("entry"), str):
        raw["entry"] = _rename(raw["entry"])

    # 2. Agent definitions — model and mcp refs
    agents = raw.get("agents", {})
    if isinstance(agents, dict):
        for agent_def in agents.values():
            if not isinstance(agent_def, dict):
                continue
            if isinstance(agent_def.get("model"), str):
                agent_def["model"] = _rename(agent_def["model"])
            if isinstance(agent_def.get("mcp"), list):
                agent_def["mcp"] = [_rename(m) for m in agent_def["mcp"]]

    # 3. MCP client server references
    clients = raw.get("mcp_clients", {})
    if isinstance(clients, dict):
        for client_def in clients.values():
            if isinstance(client_def, dict) and isinstance(client_def.get("server"), str):
                client_def["server"] = _rename(client_def["server"])

    # 4. Orchestration definitions — driven by reference_fields() descriptors
    _ORCH_DEFS = {
        "delegate": DelegateOrchestrationDef,
        "swarm": SwarmOrchestrationDef,
        "graph": GraphOrchestrationDef,
    }

    orchs = raw.get("orchestrations", {})
    if isinstance(orchs, dict):
        for orch_def in orchs.values():
            if not isinstance(orch_def, dict):
                continue
            mode = orch_def.get("mode")
            def_cls = _ORCH_DEFS.get(mode)
            if def_cls is None:
                continue
            for path_spec in def_cls.reference_fields():
                _apply_rename(orch_def, path_spec, _rename)


def _apply_rename(
    data: dict[str, Any],
    path_spec: str,
    rename_fn: Callable[[str], str],
) -> None:
    """Apply a rename function to the value(s) at a JSON path spec.

    Supported path forms:
    - ``"field"`` — simple top-level string field
    - ``"field[]"`` — each element of a top-level list
    - ``"field[].sub"`` — ``sub`` key inside each dict element of ``field``

    Args:
        data: The raw dict to mutate.
        path_spec: A simplified JSON path descriptor.
        rename_fn: A function mapping old names to new names.
    """
    parts = path_spec.split("[]")
    head = parts[0]

    if len(parts) == 1:
        # Simple field: "entry_name"
        if isinstance(data.get(head), str):
            data[head] = rename_fn(data[head])
        return

    tail = parts[1].lstrip(".")  # e.g. "agent", "from", "to", or ""
    collection = data.get(head)
    if not isinstance(collection, list):
        return

    if not tail:
        # List of strings: "agents[]"
        data[head] = [rename_fn(item) if isinstance(item, str) else item for item in collection]
    else:
        # List of dicts with a sub-field: "connections[].agent", "edges[].from"
        for item in collection:
            if isinstance(item, dict) and tail in item:
                item[tail] = rename_fn(item[tail])


def is_fs_spec(spec: str) -> bool:
    """Return True if ``spec`` looks like a filesystem import path.

    A spec is a filesystem path if the portion before the first ``:`` contains
    ``/``, ``\\``, or ends with ``.py``.  These are the same rules used by
    :func:`resolve_tool_spec` in ``tools.py``.
    """
    path_part = spec.partition(":")[0]
    return "/" in path_part or "\\" in path_part or path_part.endswith(".py")


def make_absolute(spec: str, config_dir: Path) -> str:
    """Rewrite a relative filesystem spec to an absolute path.

    Module specs and already-absolute paths are returned unchanged.

    Args:
        spec: Import or filesystem spec string.
        config_dir: Directory of the config file (anchor for relative paths).

    Returns:
        Spec with the path portion made absolute.
    """
    if not is_fs_spec(spec):
        return spec

    path_part, sep, rest = spec.partition(":")
    # Treat POSIX-style absolute paths (starting with "/") as already absolute on all
    # platforms, including Windows where Path("/...").is_absolute() returns False.
    if Path(path_part).is_absolute() or path_part.startswith("/"):
        return spec

    abs_path = str((config_dir / path_part).resolve())
    return f"{abs_path}{sep}{rest}" if sep else abs_path


def rewrite_relative_paths(raw: dict, config_dir: Path) -> None:
    """Rewrite all relative filesystem specs to absolute paths (in place).

    Every config field that accepts a ``module.path:Object`` or
    ``./file.py:Object`` import spec is rewritten so that relative
    filesystem paths are anchored to ``config_dir`` (the directory
    containing the YAML config file).  This ensures configs work
    regardless of the process working directory.

    Fields rewritten:
    - ``agents.<name>.tools[]`` — tool spec strings
    - ``agents.<name>.hooks[]`` — string import specs and ``HookDef.type``
    - ``agents.<name>.type`` — custom agent factory path
    - ``mcp_servers.<name>.type`` — MCP server factory path
    - ``models.<name>.provider`` — custom model class path
    - ``session_manager.type`` — custom session manager path

    Args:
        raw: Parsed raw config dict (mutated in place).
        config_dir: Directory of the config file being parsed.
    """
    # ── agents ────────────────────────────────────────────────────────────
    agents = raw.get("agents")
    if isinstance(agents, dict):
        for agent_def in agents.values():
            if not isinstance(agent_def, dict):
                continue

            # tools: list[str]
            tools = agent_def.get("tools")
            if isinstance(tools, list):
                agent_def["tools"] = [
                    make_absolute(s, config_dir) if isinstance(s, str) else s for s in tools
                ]

            # hooks: list[str | dict]
            hooks = agent_def.get("hooks")
            if isinstance(hooks, list):
                for i, hook in enumerate(hooks):
                    if isinstance(hook, str):
                        hooks[i] = make_absolute(hook, config_dir)
                    elif isinstance(hook, dict):
                        hook_d = cast(dict[str, Any], hook)
                        hook_type = hook_d.get("type")
                        if isinstance(hook_type, str):
                            hook_d["type"] = make_absolute(hook_type, config_dir)

            # type: str (custom agent factory)
            if isinstance(agent_def.get("type"), str):
                agent_def["type"] = make_absolute(agent_def["type"], config_dir)

    # ── mcp_servers ───────────────────────────────────────────────────────
    mcp_servers = raw.get("mcp_servers")
    if isinstance(mcp_servers, dict):
        for server_def in mcp_servers.values():
            if isinstance(server_def, dict) and isinstance(server_def.get("type"), str):
                server_def["type"] = make_absolute(server_def["type"], config_dir)

    # ── models (custom provider) ──────────────────────────────────────────
    models = raw.get("models")
    if isinstance(models, dict):
        for model_def in models.values():
            if isinstance(model_def, dict) and isinstance(model_def.get("provider"), str):
                model_def["provider"] = make_absolute(model_def["provider"], config_dir)

    # ── session_manager (root-level or per-agent — agent already handled) ─
    sm = raw.get("session_manager")
    if isinstance(sm, dict) and isinstance(sm.get("type"), str):
        sm["type"] = make_absolute(sm["type"], config_dir)

    # ── orchestrations (hooks + edge conditions on swarm/graph) ─────────
    orchestrations = raw.get("orchestrations")
    if isinstance(orchestrations, dict):
        for orch_def in orchestrations.values():
            if not isinstance(orch_def, dict):
                continue
            orch_hooks = orch_def.get("hooks")
            if isinstance(orch_hooks, list):
                for i, hook in enumerate(orch_hooks):
                    if isinstance(hook, str):
                        orch_hooks[i] = make_absolute(hook, config_dir)
                    elif isinstance(hook, dict):
                        hook_d = cast(dict[str, Any], hook)
                        hook_type = hook_d.get("type")
                        if isinstance(hook_type, str):
                            hook_d["type"] = make_absolute(hook_type, config_dir)

            # edge conditions — rewrite relative file paths
            edges = orch_def.get("edges")
            if isinstance(edges, list):
                for edge in edges:
                    if isinstance(edge, dict) and isinstance(edge.get("condition"), str):
                        edge["condition"] = make_absolute(edge["condition"], config_dir)


def parse_single_source(source: str | Path) -> dict:
    """Parse one config source into a processed raw dict.

    Handles file reading (for Path or existing file-path strings),
    anchor stripping, and per-source variable interpolation.  Relative
    filesystem tool specs are rewritten to absolute paths anchored to the
    config file's directory (not the process CWD).

    Args:
        source: File path or raw YAML string.

    Returns:
        Processed raw config dict.

    Raises:
        FileNotFoundError: If source looks like a file path but doesn't exist.
        ValueError: If source does not parse to a YAML mapping.
    """
    config_dir: Path | None = None

    if isinstance(source, Path):
        if not source.exists():
            raise FileNotFoundError(f"Config file not found: {source}")
        try:
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"Invalid YAML in {source}: {exc}") from None
        config_dir = source.resolve().parent
    else:
        path = Path(source)
        if path.is_file():
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from None
            config_dir = path.resolve().parent
        elif path.suffix in (".yaml", ".yml") or os.sep in source or "/" in source:
            raise FileNotFoundError(f"Config file not found: {source}")
        else:
            try:
                raw = yaml.safe_load(source)
            except yaml.YAMLError as exc:
                raise ConfigurationError(f"Invalid YAML in inline content: {exc}") from None

    if not isinstance(raw, dict):
        raise ValueError(f"Config must contain a YAML mapping, got {type(raw).__name__}")

    vars_block = raw.pop("vars", {})
    raw = strip_anchors(raw)
    raw = interpolate(raw, variables=vars_block, env=dict(os.environ))

    if config_dir is not None:
        rewrite_relative_paths(raw, config_dir)

    return raw


def merge_raw_configs(configs: list[dict]) -> dict:
    """Merge multiple processed raw-config dicts.

    Collection sections are combined; duplicate keys in the same section
    raise ``ValueError``. All other keys use last-wins semantics.

    Args:
        configs: List of processed raw config dicts.

    Returns:
        Single merged raw config dict.

    Raises:
        ValueError: If duplicate names are found across sources.
    """
    merged: dict = {}

    for key in COLLECTION_KEYS:
        merged[key] = {}

    for cfg in configs:
        for key in COLLECTION_KEYS:
            section = cfg.pop(key, {})
            if not isinstance(section, dict):
                continue
            duplicates = set(section) & set(merged[key])
            if duplicates:
                raise ValueError(
                    f"Duplicate names in '{key}' across config sources: {sorted(duplicates)}"
                )
            merged[key].update(section)

        merged.update(cfg)

    for key in COLLECTION_KEYS:
        if not merged[key]:
            del merged[key]

    return merged
