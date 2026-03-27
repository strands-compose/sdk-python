"""Tool loading utilities.

Provides helpers for loading ``@tool``-decorated functions from files, modules,
and directories.

Key Features:
    - Auto-detection of filesystem vs. module-based tool specs
    - Automatic @tool wrapping for explicit colon-spec lookups
    - Directory scanning with underscore-prefixed file exclusion
    - Unified spec resolver supporting files, modules, and directories
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from strands.tools.decorator import tool
from strands.tools.loader import load_tools_from_module as _strands_load_tools_from_module
from strands.types.tools import AgentTool

from ..utils import load_module_from_file

logger = logging.getLogger(__name__)


def _collect_tools(module: Any) -> list[AgentTool]:
    """Scan a module and return all ``@tool``-decorated objects.

    Only ``AgentTool`` instances (i.e. functions decorated with ``@tool``
    from strands) are collected.  Plain functions without the decorator are
    silently ignored — users must decorate them explicitly.

    Args:
        module: An imported Python module.

    Returns:
        List of AgentTool instances found in the module.
    """
    collected: list[AgentTool] = []

    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, AgentTool):
            collected.append(obj)

    return collected


def _ensure_tool(obj: Any, name: str) -> AgentTool:
    """Return *obj* as an ``AgentTool``, auto-wrapping with ``@tool`` if needed.

    Called for explicit colon-spec lookups (``file.py:func`` / ``module:func``)
    where the user has already named the exact function they want.  Wrapping is
    safe because the intent is unambiguous.  A warning is emitted so users know
    they can add ``@tool`` explicitly to silence it.

    Args:
        obj: The object retrieved from a module by name.
        name: The attribute name, used in log/error messages.

    Returns:
        An ``AgentTool`` instance.

    Raises:
        TypeError: If *obj* is not callable and cannot be wrapped as a tool.
    """
    if isinstance(obj, AgentTool):
        return obj
    if callable(obj):
        logger.warning("tool=<%s> | not decorated with @tool, wrapping automatically", name)
        return tool(obj)
    raise TypeError(f"'{name}' is not callable and cannot be used as a tool.")


def load_tools_from_file(path: str | Path) -> list[AgentTool]:
    """Load tools from a Python file.

    Imports the file as a module and collects all ``@tool``-decorated objects.
    Plain functions without the ``@tool`` decorator are silently ignored —
    users must decorate their functions explicitly.

    Args:
        path: Path to a .py file containing tool functions.

    Returns:
        List of AgentTool instances found in the file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ImportError: If the file cannot be loaded as a module.
    """
    module = load_module_from_file(path)
    return _collect_tools(module)


def load_tools_from_module(module_path: str) -> list[AgentTool]:
    """Load tools from a Python module.

    First scans for ``@tool``-decorated functions.  If none are found,
    falls back to the strands module-based tool pattern (``TOOL_SPEC`` dict
    + a function named after the module).  This ensures compatibility with
    tools like ``strands_tools.http_request`` that use the legacy pattern.

    Args:
        module_path: Dotted import path (e.g., "my_package.tools").

    Returns:
        List of AgentTool instances found in the module.

    Raises:
        ImportError: If the module cannot be imported.
        AttributeError: If the module contains neither ``@tool``-decorated
            functions nor a valid ``TOOL_SPEC`` + module-named function.
    """
    module = importlib.import_module(module_path)
    tools = _collect_tools(module)
    if tools:
        return tools

    # Fallback: delegate to strands for TOOL_SPEC-based (module) tools.
    # Strands raises AttributeError if the module has neither @tool functions
    # nor a valid TOOL_SPEC + module-named function.
    module_name = module_path.split(".")[-1]
    return _strands_load_tools_from_module(module, module_name)


def load_tool_function(spec: str) -> AgentTool:
    """Load a specific tool function from a module.

    If the named function is already decorated with ``@tool`` it is returned
    as-is.  If it is a plain callable it is automatically wrapped with
    ``@tool`` and a warning is logged — users should consider adding the
    decorator explicitly.

    Args:
        spec: Colon-separated string in "module.path:function_name" format.

    Returns:
        An ``AgentTool`` instance for the named function.

    Raises:
        ValueError: If the spec format is invalid.
        ImportError: If the module cannot be imported.
        AttributeError: If the function does not exist in the module.
        TypeError: If the named attribute is not callable.
    """
    if ":" not in spec:
        raise ValueError(f"Invalid tool spec format, expected 'module:function': {spec}")

    module_path, function_name = spec.rsplit(":", 1)
    module = importlib.import_module(module_path)
    if not hasattr(module, function_name):
        raise AttributeError(f"Module '{module_path}' has no attribute '{function_name}'")
    return _ensure_tool(getattr(module, function_name), function_name)


def load_tools_from_directory(path: str | Path) -> list[AgentTool]:
    """Load all @tool functions from .py files in a directory.

    Scans all .py files (excluding ``_``-prefixed) and loads their tools.

    Args:
        path: Directory path to scan.

    Returns:
        List of AgentTool instances from all files in the directory.

    Raises:
        FileNotFoundError: If the directory does not exist.
        NotADirectoryError: If the path is not a directory.
    """
    dir_path = Path(path).resolve()
    if not dir_path.exists():
        raise FileNotFoundError(f"Tool directory not found: {dir_path}")
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {dir_path}")

    tools: list[AgentTool] = []
    for py_file in sorted(dir_path.glob("*.py")):
        if py_file.name.startswith("_"):
            logger.debug("file=<%s> | skipping underscore-prefixed file", py_file.name)
            continue
        loaded = load_tools_from_file(py_file)
        tools.extend(loaded)
    return tools


def resolve_tool_spec(spec: str) -> list[AgentTool]:
    r"""Resolve a tool specification string to tool objects.

    Supported formats (checked in order):

    - ``"./path/to/file.py:function_name"`` — single tool from a file
    - ``"./path/to/dir/"`` or ``"./path/to/dir"`` (is a directory) — all tools in dir
    - ``"./path/to/file.py"`` or ``"path/to/file.py"`` — all tools from file
    - ``"module.path:function_name"`` — single tool from module
    - ``"module.path"`` — all tools from module

    The heuristic for path vs. module: if the spec contains ``/``, ``\\``, or
    ends with ``.py`` (before any ``:``) it is treated as a filesystem path.

    Args:
        spec: Tool specification string.

    Returns:
        List of tool objects.
    """
    # Determine the path part (before colon, if present).
    # On Windows, absolute paths contain a drive letter colon (e.g. "C:\...").
    # Strip a leading drive prefix so the colon check doesn't misfire.
    _drive = Path(spec).drive  # e.g. "C:" on Windows, "" on POSIX
    _after_drive = spec[len(_drive) :]
    path_part = _after_drive.rsplit(":", 1)[0] if ":" in _after_drive else _after_drive
    is_fs_path = "/" in path_part or "\\" in path_part or path_part.endswith(".py")

    if is_fs_path:
        if ":" in _after_drive:
            # ./path/to/file.py:function_name — single function from a file
            file_str, func_name = _after_drive.rsplit(":", 1)
            file_str = _drive + file_str
            module = load_module_from_file(file_str)
            if not hasattr(module, func_name):
                raise AttributeError(
                    f"Tool file '{Path(file_str).resolve()}' has no attribute '{func_name}'"
                )
            return [_ensure_tool(getattr(module, func_name), func_name)]

        # No colon: file or directory
        candidate = Path(spec)
        if candidate.is_dir() or spec.endswith("/") or spec.endswith("\\"):
            return list(load_tools_from_directory(candidate))

        return list(load_tools_from_file(spec))

    # Module-based specs
    if ":" in spec:
        return [load_tool_function(spec)]

    return list(load_tools_from_module(spec))


def resolve_tool_specs(specs: list[str]) -> list[AgentTool]:
    """Resolve a list of tool specification strings.

    Args:
        specs: List of tool specification strings.

    Returns:
        Flat list of all resolved tool objects.
    """
    tools: list[AgentTool] = []
    for spec in specs:
        tools.extend(resolve_tool_spec(spec))
    return tools
