"""Tool loading and wrapping utilities.

Provides helpers for:
- Loading ``@tool``-decorated functions from files, modules, and directories.
- Wrapping a ``MultiAgentBase`` as an ``AgentTool`` (``multiagent_as_tool``) for
  delegation; an ``Agent`` uses ``strands.Agent.as_tool`` directly.
- Serializing multi-agent results with full execution metadata.
"""

from __future__ import annotations

from .extractors import serialize_multiagent_result
from .loaders import (
    load_tool_function,
    load_tools_from_directory,
    load_tools_from_file,
    load_tools_from_module,
    resolve_tool_spec,
    resolve_tool_specs,
)
from .wrappers import multiagent_as_tool

__all__ = [
    "load_tool_function",
    "load_tools_from_directory",
    "load_tools_from_file",
    "load_tools_from_module",
    "multiagent_as_tool",
    "resolve_tool_spec",
    "resolve_tool_specs",
    "serialize_multiagent_result",
]
