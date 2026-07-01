"""Tool spec resolution — files, directories, and module specs -> AgentTool objects."""

from __future__ import annotations

import textwrap

import pytest
from strands.types.tools import AgentTool

from strands_compose.tools import (
    load_tool_function,
    load_tools_from_directory,
    load_tools_from_file,
    resolve_tool_spec,
    resolve_tool_specs,
)


@pytest.fixture
def tools_dir(tmp_path):
    """A directory with two @tool files plus a plain function and an ignored file."""
    d = tmp_path / "tools"
    d.mkdir()
    (d / "greet.py").write_text(
        textwrap.dedent("""\
        from strands import tool

        @tool
        def greet(name: str) -> str:
            \"\"\"Greet.\"\"\"
            return f"Hi {name}"

        def helper() -> int:
            \"\"\"Not a tool.\"\"\"
            return 1
    """)
    )
    (d / "calc.py").write_text(
        textwrap.dedent("""\
        from strands import tool

        @tool
        def add(a: int, b: int) -> int:
            \"\"\"Add.\"\"\"
            return a + b
    """)
    )
    (d / "_ignored.py").write_text("SECRET = 1\n")
    return d


def test_load_from_file_collects_only_decorated_tools(tools_dir):
    tools = load_tools_from_file(tools_dir / "greet.py")
    names = {t.tool_name for t in tools}
    assert names == {"greet"}  # plain 'helper' is ignored


def test_load_from_directory_collects_across_files_and_skips_underscore(tools_dir):
    names = {t.tool_name for t in load_tools_from_directory(tools_dir)}
    assert {"greet", "add"} <= names
    assert "SECRET" not in names


def test_load_tool_function_without_colon_raises():
    with pytest.raises(ValueError, match="tool spec"):
        load_tool_function("no_colon")


def test_resolve_file_colon_function_returns_single_tool(tools_dir):
    tools = resolve_tool_spec(f"{tools_dir / 'greet.py'}:greet")
    assert len(tools) == 1
    assert isinstance(tools[0], AgentTool)


def test_resolve_directory_spec_returns_all_tools(tools_dir):
    tools = resolve_tool_spec(f"{tools_dir}/")
    assert {t.tool_name for t in tools} >= {"greet", "add"}


def test_resolve_tool_specs_flattens_multiple_specs(tools_dir):
    tools = resolve_tool_specs([f"{tools_dir / 'greet.py'}", f"{tools_dir / 'calc.py'}"])
    assert {t.tool_name for t in tools} == {"greet", "add"}


def test_file_colon_missing_attribute_raises(tools_dir):
    with pytest.raises(AttributeError):
        resolve_tool_spec(f"{tools_dir / 'greet.py'}:missing")
