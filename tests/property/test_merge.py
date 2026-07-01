"""Property: multi-source merge unions disjoint names and always rejects duplicates."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from strands_compose.config.loaders.helpers import merge_raw_configs

_names = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=8)


@given(st.sets(_names, min_size=1, max_size=6), st.sets(_names, min_size=1, max_size=6))
def test_disjoint_sources_merge_to_the_union(names_a, names_b):
    names_b = names_b - names_a  # ensure disjoint
    cfg_a = {"agents": {n: {"system_prompt": "x"} for n in names_a}}
    cfg_b = {"agents": {n: {"system_prompt": "y"} for n in names_b}}
    merged = merge_raw_configs([cfg_a, cfg_b])
    assert set(merged.get("agents", {})) == names_a | names_b


@given(_names)
def test_duplicate_name_across_sources_always_raises(name):
    cfg_a = {"agents": {name: {"system_prompt": "x"}}}
    cfg_b = {"agents": {name: {"system_prompt": "y"}}}
    with pytest.raises(ValueError):
        merge_raw_configs([cfg_a, cfg_b])
