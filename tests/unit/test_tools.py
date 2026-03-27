"""Tests for core.tools — tool loading from files, modules, directories."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from strands.types.tools import AgentTool

from strands_compose.tools import (
    load_tool_function,
    load_tools_from_directory,
    load_tools_from_file,
    resolve_tool_spec,
)


class TestLoadToolsFromFile:
    def test_loads_tool_decorated_functions(self, tools_dir):
        tools = load_tools_from_file(tools_dir / "greet.py")
        assert len(tools) == 1
        assert tools[0].tool_name == "greet"

    def test_ignores_plain_functions(self, plain_tools_file):
        """Plain (undecorated) public functions must NOT be collected.

        Users are required to decorate their functions with @tool.
        """
        tools = load_tools_from_file(plain_tools_file)
        assert tools == []

    def test_tool_decorated_not_duplicated(self, tools_dir):
        """@tool-decorated functions should not appear twice."""
        tools = load_tools_from_file(tools_dir / "greet.py")
        names = [t.tool_name for t in tools]
        assert names.count("greet") == 1

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_tools_from_file("/nonexistent/file.py")


class TestLoadToolsFromDirectory:
    def test_loads_all_tools_from_dir(self, tools_dir):
        tools = load_tools_from_directory(tools_dir)
        names = {t.tool_name for t in tools}
        assert "greet" in names
        assert "add_numbers" in names

    def test_skips_underscore_prefixed(self, tools_dir):
        tools = load_tools_from_directory(tools_dir)
        names = {t.tool_name for t in tools}
        assert "HELPER_CONST" not in names

    def test_logs_debug_for_skipped_files(self, tools_dir, caplog):
        import logging

        with caplog.at_level(logging.DEBUG, logger="strands_compose.tools"):
            load_tools_from_directory(tools_dir)
        assert any("_helpers.py" in m and "underscore-prefixed" in m for m in caplog.messages)

    def test_nonexistent_dir_raises(self):
        with pytest.raises(FileNotFoundError):
            load_tools_from_directory("/nonexistent/dir")


class TestLoadToolFunction:
    def test_invalid_spec_raises(self):
        with pytest.raises(ValueError, match="Invalid tool spec"):
            load_tool_function("no_colon_here")


class TestResolveToolSpec:
    def test_resolve_file_spec(self, tools_dir, monkeypatch):
        monkeypatch.chdir(tools_dir.parent)
        tools = resolve_tool_spec(os.path.relpath(tools_dir / "greet.py"))
        assert len(tools) == 1

    def test_resolve_directory_spec(self, tools_dir, monkeypatch):
        monkeypatch.chdir(tools_dir.parent)
        tools = resolve_tool_spec(os.path.relpath(tools_dir) + os.sep)
        assert len(tools) >= 2

    def test_resolve_file_with_function(self, tools_dir, monkeypatch):
        monkeypatch.chdir(tools_dir.parent)
        file_path = os.path.relpath(tools_dir / "greet.py")
        tools = resolve_tool_spec(f"{file_path}:greet")
        assert len(tools) == 1

    def test_resolve_file_colon_plain_function_autowraps(
        self, plain_tools_file, caplog, monkeypatch
    ):
        """Plain function named explicitly via file colon spec is auto-wrapped.

        The function must become an AgentTool and a warning must be logged
        so the user knows to add @tool explicitly.
        """
        import logging

        monkeypatch.chdir(plain_tools_file.parent)
        file_path = os.path.relpath(plain_tools_file)
        with caplog.at_level(logging.WARNING, logger="strands_compose.tools"):
            tools = resolve_tool_spec(f"{file_path}:count_words")

        assert len(tools) == 1
        assert isinstance(tools[0], AgentTool)
        assert tools[0].tool_name == "count_words"
        assert any("count_words" in m for m in caplog.messages)
        assert any("@tool" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# Module-based tool spec resolution (R4 — coverage gap)
# ---------------------------------------------------------------------------


class TestResolveToolSpecModuleBased:
    """Test resolve_tool_spec for module-based specs (no filesystem path markers)."""

    def test_module_colon_function_loads_tool(self) -> None:
        """'module:function' spec loads a single tool via load_tool_function."""
        from unittest.mock import patch

        mock_tool = MagicMock(spec=AgentTool)

        with patch(
            "strands_compose.tools.loaders.load_tool_function", return_value=mock_tool
        ) as mock_load:
            tools = resolve_tool_spec("my_package.tools:my_func")

        mock_load.assert_called_once_with("my_package.tools:my_func")
        assert tools == [mock_tool]

    def test_module_path_loads_all_tools(self) -> None:
        """'module.path' spec (no colon) loads all tools from the module."""
        from unittest.mock import patch

        mock_tools = [MagicMock(spec=AgentTool), MagicMock(spec=AgentTool)]

        with patch(
            "strands_compose.tools.loaders.load_tools_from_module", return_value=mock_tools
        ) as mock_load:
            tools = resolve_tool_spec("my_package.tools")

        mock_load.assert_called_once_with("my_package.tools")
        assert tools == mock_tools

    def test_resolve_tool_specs_multiple(self) -> None:
        """resolve_tool_specs flattens results from multiple specs."""
        from unittest.mock import patch

        from strands_compose.tools import resolve_tool_specs

        tool1 = MagicMock(spec=AgentTool)
        tool2 = MagicMock(spec=AgentTool)

        with patch(
            "strands_compose.tools.loaders.resolve_tool_spec",
            side_effect=[[tool1], [tool2]],
        ):
            tools = resolve_tool_specs(["spec1", "spec2"])

        assert len(tools) == 2

    def test_file_colon_nonexistent_attr_raises(self, tools_dir, monkeypatch) -> None:
        """File colon spec with nonexistent function raises AttributeError."""
        monkeypatch.chdir(tools_dir.parent)
        file_path = os.path.relpath(tools_dir / "greet.py")
        with pytest.raises(AttributeError, match="has no attribute"):
            resolve_tool_spec(f"{file_path}:nonexistent_func")

    def test_not_a_directory_raises(self, tmp_path) -> None:
        """resolve_tool_spec raises NotADirectoryError for a file posing as dir."""
        f = tmp_path / "not_a_dir.py"
        f.write_text("x = 1")
        with pytest.raises(NotADirectoryError):
            from strands_compose.tools import load_tools_from_directory

            load_tools_from_directory(str(f))
