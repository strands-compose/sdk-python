"""The single import resolver — load_object over module and file specs."""

from __future__ import annotations

import sys
import textwrap

import pytest

from strands_compose.exceptions import ImportResolutionError
from strands_compose.utils import load_object


def test_loads_object_from_module_spec():
    obj = load_object("strands_compose.hooks:StopGuard")
    assert obj.__name__ == "StopGuard"


def test_loads_object_from_file_spec(tmp_path):
    mod = tmp_path / "thing.py"
    mod.write_text("VALUE = 42\n")
    assert load_object(f"{mod}:VALUE") == 42


def test_spec_without_colon_raises_import_resolution_error():
    with pytest.raises(ImportResolutionError):
        load_object("strands_compose.hooks")


def test_missing_module_raises_import_resolution_error():
    with pytest.raises(ImportResolutionError):
        load_object("no.such.module:Thing")


def test_missing_attribute_raises_import_resolution_error():
    with pytest.raises(ImportResolutionError):
        load_object("strands_compose.hooks:DoesNotExist")


def test_missing_file_attribute_raises_import_resolution_error(tmp_path):
    mod = tmp_path / "thing.py"
    mod.write_text("VALUE = 1\n")
    with pytest.raises(ImportResolutionError):
        load_object(f"{mod}:MISSING")


def test_package_file_resolves_relative_import_without_changing_sys_path(tmp_path):
    pkg = tmp_path / "hookpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "base.py").write_text("MARKER = 'from-base'\n")
    (pkg / "myhook.py").write_text(
        textwrap.dedent("""\
        from .base import MARKER

        class MyHook:
            marker = MARKER
    """)
    )
    original_sys_path = list(sys.path)

    loaded = load_object(f"{pkg / 'myhook.py'}:MyHook")

    assert loaded.marker == "from-base"
    assert sys.path == original_sys_path


def test_same_named_packages_resolve_from_their_explicit_paths(tmp_path):
    first = tmp_path / "first" / "shared"
    second = tmp_path / "second" / "shared"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "__init__.py").write_text("VALUE = 'first'\n")
    (second / "__init__.py").write_text("VALUE = 'second'\n")

    first_value = load_object(f"{first / '__init__.py'}:VALUE")
    second_value = load_object(f"{second / '__init__.py'}:VALUE")

    assert first_value == "first"
    assert second_value == "second"


def test_failed_package_initialization_can_be_retried(tmp_path):
    pkg = tmp_path / "retry_package"
    pkg.mkdir()
    init = pkg / "__init__.py"
    init.write_text("raise RuntimeError('broken')\n")

    with pytest.raises(ImportResolutionError):
        load_object(f"{init}:VALUE")

    init.write_text("VALUE = 42\n")

    assert load_object(f"{init}:VALUE") == 42
