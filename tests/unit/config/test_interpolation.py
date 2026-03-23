"""Tests for core.config.interpolation — variable interpolation."""

from __future__ import annotations

import pytest

from strands_compose.config.interpolation import interpolate, strip_anchors


class TestInterpolate:
    def test_simple_var_substitution(self):
        raw = {"key": "${MY_VAR}"}
        result = interpolate(raw, variables={"MY_VAR": "hello"}, env={})
        assert result["key"] == "hello"

    def test_env_fallback(self):
        raw = {"key": "${ENV_VAR}"}
        result = interpolate(raw, variables={}, env={"ENV_VAR": "from_env"})
        assert result["key"] == "from_env"

    def test_default_value(self):
        raw = {"key": "${MISSING:-default_val}"}
        result = interpolate(raw, variables={}, env={})
        assert result["key"] == "default_val"

    def test_missing_var_without_default_raises(self):
        raw = {"key": "${MISSING}"}
        with pytest.raises(ValueError, match=r"Variable.*MISSING.*is not set"):
            interpolate(raw, variables={}, env={})

    def test_preserves_non_string_values(self):
        raw = {"count": 42, "active": True}
        result = interpolate(raw, variables={}, env={})
        assert result == {"count": 42, "active": True}

    def test_preserves_type_for_full_var_reference(self):
        raw = {"port": "${PORT}"}
        result = interpolate(raw, variables={"PORT": 8080}, env={})
        assert result["port"] == 8080

    def test_nested_dict_interpolation(self):
        raw = {"outer": {"inner": "${VAR}"}}
        result = interpolate(raw, variables={"VAR": "nested"}, env={})
        assert result["outer"]["inner"] == "nested"

    def test_list_interpolation(self):
        raw = {"items": ["${A}", "${B}"]}
        result = interpolate(raw, variables={"A": "x", "B": "y"}, env={})
        assert result["items"] == ["x", "y"]

    def test_partial_interpolation_casts_to_str(self):
        raw = {"msg": "port=${PORT}"}
        result = interpolate(raw, variables={"PORT": 8080}, env={})
        assert result["msg"] == "port=8080"

    def test_vars_lookup_before_env(self):
        raw = {"key": "${X}"}
        result = interpolate(raw, variables={"X": "from_vars"}, env={"X": "from_env"})
        assert result["key"] == "from_vars"

    def test_cross_variable_resolution(self):
        raw = {"b": "${B}"}
        result = interpolate(raw, variables={"A": "hello", "B": "${A} world"}, env={})
        assert result["b"] == "hello world"

    def test_chain_variable_resolution(self):
        raw = {"c": "${C}"}
        result = interpolate(raw, variables={"A": "x", "B": "${A}y", "C": "${B}z"}, env={})
        assert result["c"] == "xyz"

    def test_circular_reference_raises_value_error(self):
        with pytest.raises(ValueError, match=r"Unresolved variable reference"):
            interpolate({}, variables={"A": "${B}", "B": "${A}"}, env={})

    def test_self_reference_raises_value_error(self):
        with pytest.raises(ValueError, match=r"Unresolved variable reference"):
            interpolate({}, variables={"A": "${A}"}, env={})

    def test_mixed_env_and_var_cross_resolution(self):
        raw = {"b": "${B}"}
        result = interpolate(raw, variables={"A": "${FOO}", "B": "${A}_suffix"}, env={"FOO": "bar"})
        assert result["b"] == "bar_suffix"


class TestStripAnchors:
    def test_removes_x_prefixed_keys(self):
        raw = {"x-base": {"a": 1}, "agents": {"b": 2}}
        assert strip_anchors(raw) == {"agents": {"b": 2}}

    def test_keeps_non_x_keys(self):
        raw = {"models": {}, "agents": {}}
        assert strip_anchors(raw) == raw
