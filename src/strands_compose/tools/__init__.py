"""Tool loading and wrapping utilities.

Provides helpers for:
- Loading ``@tool``-decorated functions from files, modules, and directories.
- Wrapping ``Agent`` / ``MultiAgentBase`` nodes as ``AgentTool`` instances
  (``node_as_tool``, ``node_as_async_tool``) for delegation.
"""

from __future__ import annotations

from .loaders import (
    load_tool_function,
    load_tools_from_directory,
    load_tools_from_file,
    load_tools_from_module,
    resolve_tool_spec,
    resolve_tool_specs,
)
from .wrappers import (
    node_as_async_tool,
    node_as_tool,
)

__all__ = [
    "load_tool_function",
    "load_tools_from_directory",
    "load_tools_from_file",
    "load_tools_from_module",
    "node_as_async_tool",
    "node_as_tool",
    "resolve_tool_spec",
    "resolve_tool_specs",
]
