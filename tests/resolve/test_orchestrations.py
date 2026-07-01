"""Orchestration wiring — delegate forks, swarm/graph build, node-type is enforced.

Happy paths go through the real load_session seam; the type-guard goes through the
builder directly for control. Agents use the default (offline) model — no network.
"""

from __future__ import annotations

import pytest
from strands import Agent
from strands.multiagent import Swarm
from strands.multiagent.graph import Graph

from strands_compose.config import load_session, resolve_infra
from strands_compose.config.resolvers.orchestrations.builders import build_swarm
from strands_compose.config.schema import AppConfig
from strands_compose.exceptions import ConfigurationError
from tests.factories import (
    agent_def,
    delegate_orchestration,
    graph_orchestration,
    swarm_orchestration,
)


def _resolve(config: AppConfig):
    infra = resolve_infra(config)
    return load_session(config, infra)


def test_delegate_entry_is_a_forked_agent_not_the_original():
    config = AppConfig(
        agents={"writer": agent_def(), "researcher": agent_def()},
        orchestrations={"coord": delegate_orchestration("writer", {"researcher": "research"})},
        entry="coord",
    )
    resolved = _resolve(config)

    assert isinstance(resolved.orchestrators["coord"], Agent)
    assert resolved.entry is resolved.orchestrators["coord"]
    # Delegate mode forks a new agent — the original writer is untouched.
    assert resolved.orchestrators["coord"] is not resolved.agents["writer"]
    assert "writer" in resolved.agents


def test_swarm_orchestration_builds_a_swarm():
    config = AppConfig(
        agents={"analyst": agent_def(), "reporter": agent_def()},
        orchestrations={"team": swarm_orchestration("analyst", ["analyst", "reporter"])},
        entry="team",
    )
    resolved = _resolve(config)
    assert isinstance(resolved.orchestrators["team"], Swarm)


def test_graph_orchestration_builds_a_graph():
    config = AppConfig(
        agents={"a": agent_def(), "b": agent_def()},
        orchestrations={"pipe": graph_orchestration("a", [("a", "b")])},
        entry="pipe",
    )
    resolved = _resolve(config)
    assert isinstance(resolved.orchestrators["pipe"], Graph)


def test_nested_delegate_entry_wires_the_outer_orchestration():
    config = AppConfig(
        agents={"writer": agent_def(), "researcher": agent_def(), "reviewer": agent_def()},
        orchestrations={
            "team": delegate_orchestration("writer", {"researcher": "research"}),
            "full": delegate_orchestration("reviewer", {"team": "run team"}),
        },
        entry="full",
    )
    resolved = _resolve(config)
    assert resolved.entry is resolved.orchestrators["full"]


def test_swarm_node_that_is_not_a_plain_agent_raises():
    graph = build_graph_stub()
    with pytest.raises(ConfigurationError):
        build_swarm(
            "team",
            swarm_orchestration("real", ["real", "orch"]),
            nodes={"real": _bare_agent(), "orch": graph},
            entry_name="real",
        )


def _bare_agent() -> Agent:
    return Agent(system_prompt="x")


def build_graph_stub() -> Graph:
    config = AppConfig(
        agents={"a": agent_def(), "b": agent_def()},
        orchestrations={"g": graph_orchestration("a", [("a", "b")])},
        entry="g",
    )
    return _resolve(config).orchestrators["g"]
