"""Property: interpolation resolution rules hold across arbitrary names/values."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from strands_compose.config.interpolation import interpolate

# Identifier-like variable names (no ':' / '}' / '$' which have interpolation meaning).
_names = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=48),
    min_size=1,
    max_size=12,
)
# Values with no '$' so they are not themselves re-interpolated.
_values = st.text(
    alphabet=st.characters(blacklist_characters="${}", max_codepoint=1000), max_size=20
)


@given(_names, _values)
def test_variable_value_wins_over_default(name, value):
    result = interpolate({"k": f"${{{name}:-fallback}}"}, variables={name: value}, env={})
    assert result["k"] == value


@given(_names, _values)
def test_default_used_when_variable_absent(name, default):
    result = interpolate({"k": f"${{{name}:-{default}}}"}, variables={}, env={})
    assert result["k"] == default


@given(st.text(alphabet=st.characters(blacklist_characters="${}", max_codepoint=1000), max_size=30))
def test_strings_without_placeholders_are_unchanged(text):
    result = interpolate({"k": text}, variables={}, env={})
    assert result["k"] == text


@given(_names, _values)
def test_interpolation_is_a_fixed_point(name, value):
    once = interpolate({"k": f"${{{name}}}"}, variables={name: value}, env={})
    twice = interpolate(once, variables={name: value}, env={})
    assert once == twice
