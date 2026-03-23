"""Additional edge-case tests requested by FINAL_REVIEW §7.4."""

from __future__ import annotations

import pytest

from strands_compose.config.interpolation import interpolate
from strands_compose.config.loaders.helpers import sanitize_name


class TestSanitizeNameEdgeCases:
    """Extra edge cases for sanitize_name (FINAL_REVIEW §7.4)."""

    def test_unicode_chars_removed(self):
        """Unicode characters (not alphanumeric/hyphen) should be replaced."""
        assert sanitize_name("café") == "caf"

    def test_exactly_64_chars_unchanged(self):
        name = "a" * 64
        assert sanitize_name(name) == name

    def test_65_chars_truncated(self):
        assert len(sanitize_name("a" * 65)) == 64

    def test_all_spaces(self):
        assert sanitize_name("   ") == ""

    def test_mixed_special(self):
        """Mixed special characters -> collapsed underscores."""
        assert sanitize_name("a!@#$b") == "a_b"

    def test_numbers_preserved(self):
        assert sanitize_name("agent_v2") == "agent_v2"


class TestInterpolationEdgeCases:
    """Additional edge cases for interpolation (FINAL_REVIEW §7.4)."""

    def test_multiple_placeholders_in_one_string(self):
        raw = {"msg": "${A} and ${B}"}
        result = interpolate(raw, variables={"A": "x", "B": "y"}, env={})
        assert result["msg"] == "x and y"

    def test_deeply_nested_dict(self):
        raw = {"a": {"b": {"c": {"d": "${VAR}"}}}}
        result = interpolate(raw, variables={"VAR": "deep"}, env={})
        assert result["a"]["b"]["c"]["d"] == "deep"

    def test_missing_var_in_deeply_nested_raises(self):
        raw = {"a": {"b": "${MISSING}"}}
        with pytest.raises(ValueError, match="MISSING"):
            interpolate(raw, variables={}, env={})

    def test_empty_dict_no_error(self):
        assert interpolate({}, variables={}, env={}) == {}

    def test_empty_list_no_error(self):
        raw = {"items": []}
        assert interpolate(raw, variables={}, env={}) == {"items": []}

    def test_none_value_preserved(self):
        raw = {"key": None}
        result = interpolate(raw, variables={}, env={})
        assert result["key"] is None
