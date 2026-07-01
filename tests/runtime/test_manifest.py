"""build_manifest — pure introspection of live agents/orchestrations."""

from __future__ import annotations

import pytest
from strands import Agent

from strands_compose.config import load_session, resolve_infra
from strands_compose.config.schema import AppConfig
from strands_compose.manifest import build_manifest
from tests.factories import agent_def, graph_orchestration
from tests.fakes import FakeModel


def test_manifest_describes_each_agent_with_its_model():
    agent = Agent(model=FakeModel(model_id="fake-1"), name="a")
    manifest = build_manifest({"a": agent}, {}, agent)

    assert [d.name for d in manifest.agents] == ["a"]
    assert manifest.agents[0].model.model_id == "fake-1"


def test_entry_descriptor_identifies_the_entry_agent():
    agent = Agent(model=FakeModel())
    manifest = build_manifest({"a": agent}, {}, agent)
    assert manifest.entry.name == "a"
    assert manifest.entry.kind == "agent"


def test_graph_orchestration_topology_is_described():
    config = AppConfig(
        agents={"a": agent_def(), "b": agent_def()},
        orchestrations={"pipe": graph_orchestration("a", [("a", "b")])},
        entry="pipe",
    )
    resolved = load_session(config, resolve_infra(config))
    manifest = build_manifest(resolved.agents, resolved.orchestrators, resolved.entry)

    pipe = next(o for o in manifest.orchestrations if o.name == "pipe")
    assert pipe.kind == "graph"
    assert {n.id for n in pipe.nodes} == {"a", "b"}
    assert manifest.entry.kind == "orchestration"


def test_entry_not_among_nodes_raises():
    orphan = Agent(model=FakeModel())
    with pytest.raises(ValueError):
        build_manifest({}, {}, orphan)


def test_agent_session_manager_descriptor_reports_file_provider(tmp_path):
    from strands.session import FileSessionManager

    sm = FileSessionManager(session_id="s1", storage_dir=str(tmp_path))
    agent = Agent(model=FakeModel(), session_manager=sm)
    manifest = build_manifest({"a": agent}, {}, agent)
    descriptor = manifest.agents[0].session_manager
    assert descriptor is not None
    assert descriptor.provider == "file"


def test_delegate_orchestration_agent_is_listed_in_manifest_agents():
    from tests.factories import delegate_orchestration

    config = AppConfig(
        agents={"writer": agent_def(), "researcher": agent_def()},
        orchestrations={"coord": delegate_orchestration("writer", {"researcher": "d"})},
        entry="coord",
    )
    resolved = load_session(config, resolve_infra(config))
    manifest = build_manifest(resolved.agents, resolved.orchestrators, resolved.entry)
    # The forked delegate agent reports usage under its own name, so it appears in agents.
    assert "coord" in {d.name for d in manifest.agents}


def test_swarm_topology_reports_nodes_and_entry():
    from tests.factories import swarm_orchestration

    config = AppConfig(
        agents={"a": agent_def(), "b": agent_def()},
        orchestrations={"team": swarm_orchestration("a", ["a", "b"])},
        entry="team",
    )
    resolved = load_session(config, resolve_infra(config))
    manifest = build_manifest(resolved.agents, resolved.orchestrators, resolved.entry)
    team = next(o for o in manifest.orchestrations if o.name == "team")
    assert team.kind == "swarm"
    assert {n.id for n in team.nodes} == {"a", "b"}
    assert team.entry_node_id == "a"
