"""Resolve HookDef / HookEntry -> strands HookProvider instance."""

from __future__ import annotations

from strands.hooks import HookProvider

from ...utils import load_object
from ..schema import HookDef


def resolve_hook(hook_def: HookDef) -> HookProvider:
    """Resolve a HookDef to a HookProvider instance.

    ``type`` must be one of:

    - ``"module.path:ClassName"`` -- full import path (e.g.
      ``"strands_compose.hooks:StopGuard"``)
    - ``"./path/to/hooks.py:ClassName"`` -- file-based import

    No short-name aliases are supported.  Use the full import path so that
    submodules and third-party hooks work without ambiguity.

    Args:
        hook_def: Hook definition from YAML.

    Returns:
        Instantiated HookProvider.

    Raises:
        ImportResolutionError: If ``type`` is not a valid ``module:Class`` /
            ``./file.py:Class`` spec (a ``ValueError`` subclass, from ``load_object``).
        TypeError: If the resolved object is not a HookProvider subclass.
    """

    cls = load_object(hook_def.type, target="hook")

    hook = cls(**hook_def.params)
    if not isinstance(hook, HookProvider):
        raise TypeError(
            f"Hook {hook_def.type!r} returned {type(hook).__name__}, expected HookProvider subclass."
        )
    return hook


def resolve_hook_entry(entry: HookDef | str) -> HookProvider:
    """Resolve a single hook entry from an AgentDef.

    Accepts either:

    - A **string** -- treated directly as a ``module:ClassName`` or
      ``./file.py:ClassName`` import spec.
    - An inline **HookDef** -- resolved via its ``type`` and ``params``.

    Args:
        entry: Import-path string or inline HookDef.

    Returns:
        Instantiated HookProvider.
    """
    hook_def = HookDef(type=entry) if isinstance(entry, str) else entry
    return resolve_hook(hook_def)
