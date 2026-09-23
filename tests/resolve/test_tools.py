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
    nested = d / "nested"
    nested.mkdir()
    (nested / "deep.py").write_text(
        textwrap.dedent("""\
        from strands import tool

        @tool
        def deep(value: str) -> str:
            \"\"\"Deep.\"\"\"
            return value
    """)
    )
    private = d / "_private"
    private.mkdir()
    (private / "hidden.py").write_text(
        textwrap.dedent("""\
        from strands import tool

        @tool
        def hidden() -> str:
            \"\"\"Hidden.\"\"\"
            return "no"
    """)
    )
    return d


@pytest.fixture
def tool_package(tmp_path):
    """A regular package whose tool modules use relative imports."""
    pkg = tmp_path / "relpkg"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "helper.py").write_text("PREFIX = 'Hi'\n")
    (pkg / "greet.py").write_text(
        textwrap.dedent("""\
        from strands import tool

        from .helper import PREFIX

        @tool
        def greet(name: str) -> str:
            \"\"\"Greet.\"\"\"
            return f"{PREFIX} {name}"
    """)
    )
    (pkg / "sub" / "__init__.py").write_text("")
    (pkg / "sub" / "deep.py").write_text(
        textwrap.dedent("""\
        from strands import tool

        from ..helper import PREFIX

        @tool
        def deep(value: str) -> str:
            \"\"\"Deep.\"\"\"
            return f"{PREFIX}:{value}"
    """)
    )
    return pkg


def test_package_file_resolves_relative_imports(tool_package):
    tools = resolve_tool_spec(str(tool_package / "greet.py"))
    assert {tool.tool_name for tool in tools} == {"greet"}


def test_nested_package_file_resolves_parent_relative_imports(tool_package):
    tools = resolve_tool_spec(str(tool_package / "sub" / "deep.py"))
    assert {tool.tool_name for tool in tools} == {"deep"}


def test_package_directory_discovers_tools_recursively(tool_package):
    names = {tool.tool_name for tool in resolve_tool_spec(str(tool_package))}
    assert names == {"greet", "deep"}


def test_load_from_file_collects_only_decorated_tools(tools_dir):
    tools = load_tools_from_file(tools_dir / "greet.py")
    names = {t.tool_name for t in tools}
    assert names == {"greet"}  # plain 'helper' is ignored


def test_load_from_directory_collects_across_files_and_skips_underscore(tools_dir):
    names = {t.tool_name for t in load_tools_from_directory(tools_dir)}
    assert {"greet", "add"} <= names
    assert "SECRET" not in names


def test_load_from_directory_recurses_into_subdirectories(tools_dir):
    names = {t.tool_name for t in load_tools_from_directory(tools_dir)}
    assert "deep" in names


def test_load_from_directory_skips_private_subdirectories(tools_dir):
    names = {t.tool_name for t in load_tools_from_directory(tools_dir)}
    assert "hidden" not in names


def test_load_from_directory_loads_same_stem_in_two_subdirs(tmp_path):
    """Recursion must not let two files with the same name shadow each other."""
    root = tmp_path / "dup"
    for sub, tool_name in (("a", "alpha"), ("b", "beta")):
        (root / sub).mkdir(parents=True)
        (root / sub / "shared.py").write_text(
            textwrap.dedent(f"""\
            from strands import tool

            @tool
            def {tool_name}() -> str:
                \"\"\"Tool.\"\"\"
                return "{tool_name}"
        """)
        )
    names = {t.tool_name for t in load_tools_from_directory(root)}
    assert names == {"alpha", "beta"}


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
