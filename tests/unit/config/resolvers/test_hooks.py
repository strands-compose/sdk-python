"""Tests for core.config.resolvers.hooks — resolve_hook and resolve_hook_entry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from strands_compose.config.resolvers.hooks import (
    resolve_hook,
    resolve_hook_entry,
)
from strands_compose.config.schema import HookDef


class TestResolveHook:
    def test_valid_import_path(self):
        hook_def = HookDef(
            type="strands_compose.hooks.max_calls_guard:MaxToolCallsGuard",
            params={"max_calls": 10},
        )
        hook = resolve_hook(hook_def)
        assert hook.max_calls == 10  # ty: ignore

    def test_no_colon_raises(self):
        hook_def = HookDef(type="not_a_valid_spec")
        with pytest.raises(ValueError, match="not a valid import spec"):
            resolve_hook(hook_def)

    def test_file_based_hook(self, tmp_path):
        hook_file = tmp_path / "my_hook.py"
        hook_file.write_text(
            "from strands.hooks import HookProvider, HookRegistry\n"
            "from typing import Any\n"
            "class MyHook(HookProvider):\n"
            "    def __init__(self, x=1):\n"
            "        self.x = x\n"
            "    def register_hooks(self, registry: HookRegistry, **kw: Any) -> None:\n"
            "        pass\n"
        )
        hook_def = HookDef(type=f"{hook_file}:MyHook", params={"x": 42})
        hook = resolve_hook(hook_def)
        assert hook.x == 42  # ty: ignore

    def test_non_hook_provider_raises(self, tmp_path):
        hook_file = tmp_path / "bad_hook.py"
        hook_file.write_text("class NotAHook:\n    pass\n")
        hook_def = HookDef(type=f"{hook_file}:NotAHook")
        with pytest.raises(TypeError, match="expected HookProvider subclass"):
            resolve_hook(hook_def)

    @patch("strands_compose.config.resolvers.hooks.load_object")
    def test_non_hook_provider_module_path_raises(self, mock_import):
        mock_import.return_value = MagicMock(return_value="not_a_hook_provider")
        hook_def = HookDef(type="some.module:BadHook")
        with pytest.raises(TypeError, match="expected HookProvider subclass"):
            resolve_hook(hook_def)


class TestLoadHookFromFile:
    def test_missing_class_raises(self, tmp_path):
        hook_file = tmp_path / "empty_hook.py"
        hook_file.write_text("# no classes here\n")
        hook_def = HookDef(type=f"{hook_file}:MissingClass")
        with pytest.raises(ValueError, match="has no attribute 'MissingClass'"):
            resolve_hook(hook_def)


class TestResolveHookEntry:
    def test_string_entry(self):
        hook = resolve_hook_entry(
            "strands_compose.hooks.max_calls_guard:MaxToolCallsGuard",
        )
        assert hook.max_calls == 25  # default  # ty: ignore

    def test_hook_def_entry(self):
        entry = HookDef(
            type="strands_compose.hooks.max_calls_guard:MaxToolCallsGuard",
            params={"max_calls": 5},
        )
        hook = resolve_hook_entry(entry)
        assert hook.max_calls == 5  # ty: ignore
