"""End-to-end load() wiring over worked YAML fixtures — the thin top layer.

Asserts the whole pipeline wires up and the entry object has the right type/
topology. Business rules are proven in resolve/; this only guards the flow.
"""

from __future__ import annotations

import pytest
from strands import Agent

from strands_compose.config import ResolvedConfig, load

pytestmark = pytest.mark.integration


def test_minimal_config_wires_entry_agent(fixture_path):
    resolved = load(fixture_path("minimal.yaml"))
    assert isinstance(resolved, ResolvedConfig)
    assert isinstance(resolved.entry, Agent)
    assert "greeter" in resolved.agents


def test_multiple_sources_are_merged(fixture_path):
    resolved = load(
        [fixture_path("multi_source_base.yaml"), fixture_path("multi_source_extra.yaml")]
    )
    assert {"planner", "helper"} <= set(resolved.agents)
