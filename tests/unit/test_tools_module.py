"""Tests for tools.load_tools_from_module."""

from __future__ import annotations

import sys
import types

import pytest
from strands.tools.decorator import tool
from strands.types.tools import AgentTool

from strands_compose.tools import load_tools_from_module


class TestLoadToolsFromModule:
    """Unit tests for load_tools_from_module()."""

    def test_loads_tool_decorated_functions(self, tmp_path):
        """Creates a temporary module with @tool functions and loads them."""
        mod = types.ModuleType("_test_module_with_tools")

        @tool
        def greet(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}!"

        setattr(mod, "greet", greet)
        sys.modules["_test_module_with_tools"] = mod
        try:
            tools = load_tools_from_module("_test_module_with_tools")
            assert len(tools) == 1
            assert isinstance(tools[0], AgentTool)
            assert tools[0].tool_name == "greet"
        finally:
            sys.modules.pop("_test_module_with_tools", None)

    def test_ignores_plain_functions(self):
        """Plain (undecorated) public functions must NOT be collected."""
        mod = types.ModuleType("_test_module_plain")
        setattr(mod, "plain_func", lambda: None)
        sys.modules["_test_module_plain"] = mod
        try:
            tools = load_tools_from_module("_test_module_plain")
            assert tools == []
        finally:
            sys.modules.pop("_test_module_plain", None)

    def test_ignores_private_attributes(self):
        """Underscore-prefixed attributes should be skipped."""
        mod = types.ModuleType("_test_module_private")

        @tool
        def _private_tool(x: int) -> int:
            """Private tool."""
            return x

        setattr(mod, "_private_tool", _private_tool)
        sys.modules["_test_module_private"] = mod
        try:
            tools = load_tools_from_module("_test_module_private")
            assert tools == []
        finally:
            sys.modules.pop("_test_module_private", None)

    def test_nonexistent_module_raises(self):
        with pytest.raises(ImportError):
            load_tools_from_module("nonexistent.module.path")

    def test_multiple_tools_collected(self):
        """Module with multiple @tool functions returns all of them."""
        mod = types.ModuleType("_test_module_multi")

        @tool
        def tool_a(x: int) -> int:
            """Tool A."""
            return x

        @tool
        def tool_b(y: str) -> str:
            """Tool B."""
            return y

        setattr(mod, "tool_a", tool_a)
        setattr(mod, "tool_b", tool_b)
        sys.modules["_test_module_multi"] = mod
        try:
            tools = load_tools_from_module("_test_module_multi")
            names = {t.tool_name for t in tools}
            assert "tool_a" in names
            assert "tool_b" in names
        finally:
            sys.modules.pop("_test_module_multi", None)
