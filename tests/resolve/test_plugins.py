"""PluginDef / plugin entry -> live strands Plugin resolution."""

from __future__ import annotations

import pytest
from strands.plugins import Plugin

from strands_compose.config.resolvers.plugins import resolve_plugin, resolve_plugin_entry
from strands_compose.config.schema import PluginDef
from strands_compose.exceptions import ImportResolutionError
from tests.fakes import FakePlugin, fake_plugin_factory  # noqa: F401


def test_plugin_type_without_colon_raises_import_resolution_error():
    with pytest.raises(ImportResolutionError):
        resolve_plugin(PluginDef(type="no_colon_here"))


def test_plugin_resolving_to_non_plugin_raises_type_error():
    with pytest.raises(TypeError):
        resolve_plugin(PluginDef(type="builtins:dict"))


def test_plugin_class_with_params_resolves_to_plugin_instance():
    plugin = resolve_plugin(PluginDef(type="tests.fakes:FakePlugin", params={"prefix": "hello"}))
    assert isinstance(plugin, FakePlugin)
    assert plugin.prefix == "hello"


def test_plugin_factory_resolves_to_plugin_instance():
    plugin = resolve_plugin(
        PluginDef(type="tests.fakes:fake_plugin_factory", params={"prefix": "via-factory"})
    )
    assert isinstance(plugin, FakePlugin)
    assert plugin.prefix == "via-factory"


def test_bare_string_entry_is_treated_as_import_spec():
    plugin = resolve_plugin_entry("tests.fakes:FakePlugin")
    assert isinstance(plugin, Plugin)
