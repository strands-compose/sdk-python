"""End-to-end load() wiring over worked YAML fixtures — the thin top layer.

Asserts the whole pipeline wires up and the entry object has the right type/
topology. Business rules are proven in resolve/; this only guards the flow.
"""

from __future__ import annotations

import pytest
from strands import Agent

from strands_compose.config import ResolvedConfig, load
from tests.factories import write_config

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


def test_package_tools_resolve_relative_to_config_file(tmp_path, monkeypatch):
    config_dir = tmp_path / "app"
    package = config_dir / "toolkit"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "shared.py").write_text("PREFIX = 'local'\n")
    (package / "search.py").write_text(
        "from strands import tool\n"
        "from .shared import PREFIX\n\n"
        "@tool\n"
        "def search() -> str:\n"
        '    """Search."""\n'
        "    return PREFIX\n"
    )
    config = write_config(
        config_dir,
        """
        agents:
          assistant:
            tools: [./toolkit]
        entry: assistant
        """,
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    resolved = load(config)

    assert isinstance(resolved.entry, Agent)
    assert "search" in resolved.entry.tool_names
