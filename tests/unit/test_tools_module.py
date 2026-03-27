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

    def test_plain_functions_without_tool_spec_raises(self):
        """Module with only plain functions and no TOOL_SPEC raises AttributeError."""
        mod = types.ModuleType("_test_module_plain")
        setattr(mod, "plain_func", lambda: None)
        sys.modules["_test_module_plain"] = mod
        try:
            with pytest.raises(AttributeError, match="not a valid module"):
                load_tools_from_module("_test_module_plain")
        finally:
            sys.modules.pop("_test_module_plain", None)

    def test_private_only_module_falls_back_to_strands(self):
        """Module with only _-prefixed @tool functions falls back to strands which finds them."""
        mod = types.ModuleType("_test_module_private")

        @tool
        def _private_tool(x: int) -> int:
            """Private tool."""
            return x

        setattr(mod, "_private_tool", _private_tool)
        sys.modules["_test_module_private"] = mod
        try:
            tools = load_tools_from_module("_test_module_private")
            assert len(tools) == 1
            assert tools[0].tool_name == "_private_tool"
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

    def test_tool_spec_module_fallback(self):
        """Module with TOOL_SPEC + same-name function is loaded via strands fallback."""
        mod = types.ModuleType("_test_module_spec")
        setattr(
            mod,
            "TOOL_SPEC",
            {
                "name": "_test_module_spec",
                "description": "A test module-based tool",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                        },
                        "required": ["query"],
                    }
                },
            },
        )

        def _test_module_spec(tool_use, **kwargs):
            return {"status": "success", "content": [{"text": "ok"}], "toolUseId": "t1"}

        setattr(mod, "_test_module_spec", _test_module_spec)
        sys.modules["_test_module_spec"] = mod
        try:
            tools = load_tools_from_module("_test_module_spec")
            assert len(tools) == 1
            assert tools[0].tool_name == "_test_module_spec"
        finally:
            sys.modules.pop("_test_module_spec", None)

    def test_tool_spec_fallback_missing_function_raises(self):
        """Module with TOOL_SPEC but no matching function raises AttributeError."""
        mod = types.ModuleType("_test_module_no_func")
        setattr(
            mod,
            "TOOL_SPEC",
            {
                "name": "_test_module_no_func",
                "description": "Missing function",
                "inputSchema": {"json": {"type": "object", "properties": {}}},
            },
        )
        sys.modules["_test_module_no_func"] = mod
        try:
            with pytest.raises(AttributeError):
                load_tools_from_module("_test_module_no_func")
        finally:
            sys.modules.pop("_test_module_no_func", None)

    def test_decorated_tools_take_priority_over_tool_spec(self):
        """When both @tool functions and TOOL_SPEC exist, @tool wins."""
        mod = types.ModuleType("_test_module_both")

        @tool
        def my_tool(x: int) -> int:
            """A decorated tool."""
            return x

        setattr(mod, "my_tool", my_tool)
        setattr(
            mod,
            "TOOL_SPEC",
            {
                "name": "_test_module_both",
                "description": "Should be ignored",
                "inputSchema": {"json": {"type": "object", "properties": {}}},
            },
        )
        sys.modules["_test_module_both"] = mod
        try:
            tools = load_tools_from_module("_test_module_both")
            assert len(tools) == 1
            assert tools[0].tool_name == "my_tool"
        finally:
            sys.modules.pop("_test_module_both", None)
