"""Property: name sanitization always yields a safe, idempotent identifier."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from strands_compose.config.loaders.helpers import sanitize_name

_SAFE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


@given(st.text(min_size=1, max_size=80))
def test_sanitized_name_contains_only_safe_characters(raw):
    assert set(sanitize_name(raw)) <= _SAFE


@given(st.text(min_size=1, max_size=80))
def test_sanitized_name_never_exceeds_64_chars(raw):
    assert len(sanitize_name(raw)) <= 64


@given(st.text(min_size=1, max_size=80))
def test_sanitization_is_idempotent(raw):
    once = sanitize_name(raw)
    # Only meaningful when the first pass produced a non-empty name.
    if once:
        assert sanitize_name(once) == once
