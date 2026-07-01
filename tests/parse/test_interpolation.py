"""Interpolation of ${VAR} / ${VAR:-default} and anchor stripping (parse layer)."""

from __future__ import annotations

import pytest

from strands_compose.config.interpolation import interpolate, strip_anchors


def test_var_resolves_from_variables_block():
    result = interpolate({"model": "${MODEL}"}, variables={"MODEL": "claude"}, env={})
    assert result["model"] == "claude"


def test_var_resolves_from_env_when_absent_in_variables():
    result = interpolate({"model": "${MODEL}"}, variables={}, env={"MODEL": "from-env"})
    assert result["model"] == "from-env"


def test_variables_take_precedence_over_env():
    result = interpolate({"m": "${X}"}, variables={"X": "vars"}, env={"X": "env"})
    assert result["m"] == "vars"


def test_default_used_when_var_unset():
    result = interpolate({"region": "${REGION:-us-east-1}"}, variables={}, env={})
    assert result["region"] == "us-east-1"


def test_missing_var_without_default_raises():
    with pytest.raises(ValueError, match="MISSING"):
        interpolate({"x": "${MISSING}"}, variables={}, env={})


def test_whole_string_reference_preserves_non_string_type():
    result = interpolate({"n": "${COUNT}"}, variables={"COUNT": 7}, env={})
    assert result["n"] == 7


def test_partial_reference_is_concatenated_as_string():
    result = interpolate({"greeting": "hi ${NAME}!"}, variables={"NAME": "Bob"}, env={})
    assert result["greeting"] == "hi Bob!"


def test_cross_variable_chain_resolves():
    result = interpolate(
        {"out": "${B}"},
        variables={"A": "x", "B": "${A}y"},
        env={},
    )
    assert result["out"] == "xy"


def test_circular_variable_reference_raises():
    with pytest.raises(ValueError):
        interpolate({"out": "${A}"}, variables={"A": "${B}", "B": "${A}"}, env={})


def test_nested_structures_are_interpolated():
    result = interpolate(
        {"agents": {"a": {"tools": ["${TOOL}"]}}},
        variables={"TOOL": "mod:fn"},
        env={},
    )
    assert result["agents"]["a"]["tools"] == ["mod:fn"]


def test_input_dict_is_not_mutated():
    raw = {"m": "${X}"}
    interpolate(raw, variables={"X": "v"}, env={})
    assert raw == {"m": "${X}"}


def test_strip_anchors_removes_top_level_x_keys():
    result = strip_anchors({"x-common": {"a": 1}, "agents": {}})
    assert "x-common" not in result
    assert "agents" in result
