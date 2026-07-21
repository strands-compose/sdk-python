"""Resolve PluginDef / plugin entry -> strands.plugins.Plugin instance."""

from __future__ import annotations

from strands.plugins import Plugin

from ...utils import load_object
from ..schema import PluginDef


def resolve_plugin(plugin_def: PluginDef) -> Plugin:
    """Resolve a PluginDef to a Plugin instance.

    ``type`` must be one of:

    - ``"module.path:ClassName"`` -- full import path (e.g.
      ``"strands:AgentSkills"``)
    - ``"./path/to/plugins.py:ClassName"`` -- file-based import

    No short-name aliases are supported.  Use the full import path so that
    submodules and third-party plugins work without ambiguity.

    Args:
        plugin_def: Plugin definition from YAML.

    Returns:
        Instantiated Plugin.

    Raises:
        ValueError: If ``type`` is not in ``module:Class`` format.
        TypeError: If calling the resolved object does not produce a Plugin.
    """

    type_str = plugin_def.type
    if ":" not in type_str:
        raise ValueError(
            f"Plugin type {type_str!r} is not a valid import spec.\n"
            f"Use 'module.path:ClassName' (e.g. 'strands:AgentSkills') "
            f"or './path/to/file.py:ClassName'."
        )

    obj = load_object(type_str, target="plugin")

    plugin = obj(**plugin_def.params)
    if not isinstance(plugin, Plugin):
        raise TypeError(
            f"Plugin {type_str!r} returned {type(plugin).__name__}, "
            f"expected strands.plugins.Plugin subclass."
        )
    return plugin


def resolve_plugin_entry(entry: PluginDef | str) -> Plugin:
    """Resolve a single plugin entry from an AgentDef.

    Accepts either:

    - A **string** -- treated directly as a ``module:ClassName`` or
      ``./file.py:ClassName`` import spec.
    - An inline **PluginDef** -- resolved via its ``type`` and ``params``.

    Args:
        entry: Import-path string or inline PluginDef.

    Returns:
        Instantiated Plugin.
    """
    plugin_def = PluginDef(type=entry) if isinstance(entry, str) else entry
    return resolve_plugin(plugin_def)
