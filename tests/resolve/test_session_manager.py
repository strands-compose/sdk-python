"""SessionManagerDef resolution and the uniform leaf-chain precedence."""

from __future__ import annotations

import pytest
from strands.multiagent import Swarm
from strands.multiagent.graph import Graph
from strands.session import FileSessionManager, SnapshotSessionManager
from strands.session.session_manager import SessionManager
from strands.storage import LocalFileStorage, S3Storage

from strands_compose.config import load
from strands_compose.config.resolvers.session_manager import (
    resolve_leaf_session_manager,
    resolve_session_manager,
    resolve_snapshot_storage,
)
from strands_compose.config.schema import AppConfig, SessionManagerDef
from strands_compose.exceptions import ConfigurationError
from strands_compose.manifest import build_manifest
from tests.factories import agent_def, graph_orchestration, model_def, swarm_orchestration


def test_file_provider_resolves_to_file_session_manager(tmp_path):
    sm = resolve_session_manager(
        SessionManagerDef(
            provider="file", params={"session_id": "s1", "storage_dir": str(tmp_path)}
        )
    )
    assert isinstance(sm, FileSessionManager)


def test_session_id_override_wins_over_params(tmp_path):
    sm = resolve_session_manager(
        SessionManagerDef(
            provider="file", params={"session_id": "from-params", "storage_dir": str(tmp_path)}
        ),
        session_id_override="from-runtime",
    )
    assert isinstance(sm, FileSessionManager)
    assert sm.session_id == "from-runtime"


def test_unknown_provider_raises_value_error():
    with pytest.raises(ValueError, match="provider"):
        resolve_session_manager(SessionManagerDef(provider="quantum"))


def test_custom_type_not_a_session_manager_raises_type_error():
    with pytest.raises(TypeError):
        resolve_session_manager(SessionManagerDef(type="builtins:dict"))


# ── Leaf chain precedence ──────────────────────────────────────────────────


def test_leaf_override_wins_over_global(tmp_path):
    leaf = SessionManagerDef(provider="file", params={"storage_dir": str(tmp_path)})
    result = resolve_leaf_session_manager(
        leaf_def=leaf, leaf_is_set=True, global_def=None, session_id="s"
    )
    assert isinstance(result, SessionManager)


def test_explicit_opt_out_returns_none_even_with_global(tmp_path):
    glob = SessionManagerDef(provider="file", params={"storage_dir": str(tmp_path)})
    result = resolve_leaf_session_manager(
        leaf_def=None, leaf_is_set=True, global_def=glob, session_id="s"
    )
    assert result is None


def test_global_default_used_when_leaf_absent(tmp_path):
    glob = SessionManagerDef(provider="file", params={"storage_dir": str(tmp_path)})
    result = resolve_leaf_session_manager(
        leaf_def=None, leaf_is_set=False, global_def=glob, session_id="s"
    )
    assert isinstance(result, SessionManager)


def test_no_leaf_no_global_returns_none():
    result = resolve_leaf_session_manager(
        leaf_def=None, leaf_is_set=False, global_def=None, session_id=None
    )
    assert result is None


# ── load-level composition ─────────────────────────────────────────────────


def test_global_agentcore_provider_is_rejected():
    # agentcore needs a unique actor_id per agent, so it can't be a global default.
    config = AppConfig(
        agents={"a": agent_def()},
        entry="a",
        session_manager=SessionManagerDef(provider="agentcore"),
    )
    with pytest.raises(ValueError, match="agentcore"):
        load(config)


def test_global_session_manager_propagates_to_the_built_entry_agent(tmp_path, fake_runtime):
    config = AppConfig(
        models={"m": model_def()},
        agents={"a": agent_def(model="m")},
        entry="a",
        session_manager=SessionManagerDef(provider="file", params={"storage_dir": str(tmp_path)}),
    )
    resolved = load(config, session_id="s1")

    # Observe via the manifest (public introspection), not private agent state.
    manifest = build_manifest(resolved.agents, resolved.orchestrators, resolved.entry)
    assert manifest.agents[0].session_manager is not None
    assert manifest.agents[0].session_manager.provider == "file"


def test_each_load_builds_isolated_agents(tmp_path, fake_runtime):
    # One parsed config, many sessions — each gets its own agents.
    config = AppConfig(
        models={"m": model_def()},
        agents={"a": agent_def(model="m")},
        entry="a",
        session_manager=SessionManagerDef(provider="file", params={"storage_dir": str(tmp_path)}),
    )

    r1 = load(config, session_id="s1")
    r2 = load(config, session_id="s2")

    assert r1.agents["a"] is not r2.agents["a"]


# ── snapshot providers ─────────────────────────────────────────────────────


def _file_snapshot(tmp_path) -> SessionManagerDef:
    return SessionManagerDef(provider="file-snapshot", params={"storage_dir": str(tmp_path)})


def test_file_snapshot_provider_resolves_to_snapshot_session_manager(tmp_path):
    sm = resolve_session_manager(_file_snapshot(tmp_path), session_id_override="s1")
    assert isinstance(sm, SnapshotSessionManager)
    assert sm.session_id == "s1"


@pytest.mark.parametrize("prefix", [None, "", "p/"])
def test_s3_snapshot_provider_builds_storage_without_network(prefix):
    # No agent is built, so nothing reads S3: S3Storage creates its client lazily.
    session_def = SessionManagerDef(
        provider="s3-snapshot", params={"bucket": "b", "prefix": prefix}
    )
    assert isinstance(resolve_snapshot_storage(session_def), S3Storage)
    assert isinstance(resolve_session_manager(session_def), SnapshotSessionManager)


def test_repository_providers_build_no_snapshot_storage(tmp_path):
    file_def = SessionManagerDef(provider="file", params={"storage_dir": str(tmp_path)})
    assert resolve_snapshot_storage(file_def) is None


def test_file_snapshot_agent_shares_its_storage_and_restores_history(tmp_path, fake_runtime):
    config = AppConfig(
        models={"m": model_def()},
        agents={"a": agent_def(model="m")},
        entry="a",
        session_manager=_file_snapshot(tmp_path),
    )
    load(config, session_id="s1").agents["a"]("remember this")

    restored = load(config, session_id="s1").agents["a"]

    assert isinstance(restored.storage, LocalFileStorage)
    assert restored.messages


def test_snapshot_provider_works_with_a_context_manager(tmp_path, fake_runtime):
    config = AppConfig(
        models={"m": model_def()},
        agents={"a": agent_def(model="m", agent_kwargs={"context_manager": "auto"})},
        entry="a",
        session_manager=_file_snapshot(tmp_path),
    )
    agent = load(config, session_id="s1").agents["a"]
    agent("hi")
    assert agent.context_manager is not None
    assert agent.context_manager.stash_is_durable  # the stash uses the shared session storage


def test_swarm_orchestration_accepts_a_snapshot_provider(tmp_path, fake_runtime):
    config = AppConfig(
        models={"m": model_def()},
        agents={
            "a": agent_def(model="m", description="first"),
            "b": agent_def(model="m", description="second"),
        },
        orchestrations={
            "team": swarm_orchestration("a", ["a", "b"], session_manager=_file_snapshot(tmp_path))
        },
        entry="team",
    )
    swarm = load(config, session_id="s1").orchestrators["team"]
    assert isinstance(swarm, Swarm)
    assert isinstance(swarm.session_manager, SnapshotSessionManager)
    swarm("hi")  # proves manager-level storage is present; strands raises without it


def test_graph_orchestration_accepts_a_snapshot_provider(tmp_path, fake_runtime):
    config = AppConfig(
        models={"m": model_def()},
        agents={"a": agent_def(model="m"), "b": agent_def(model="m")},
        orchestrations={
            "flow": graph_orchestration("a", [("a", "b")], session_manager=_file_snapshot(tmp_path))
        },
        entry="flow",
    )
    graph = load(config, session_id="s1").orchestrators["flow"]
    assert isinstance(graph, Graph)
    assert isinstance(graph.session_manager, SnapshotSessionManager)
    graph("hi")


def test_custom_agent_factory_receives_the_snapshot_storage(tmp_path, fake_runtime):
    config = AppConfig(
        models={"m": model_def()},
        agents={"a": agent_def(model="m", type="strands:Agent")},
        entry="a",
        session_manager=_file_snapshot(tmp_path),
    )
    assert isinstance(load(config).agents["a"].storage, LocalFileStorage)


def test_agent_kwargs_storage_conflicts_with_a_snapshot_provider(tmp_path, fake_runtime):
    config = AppConfig(
        models={"m": model_def()},
        agents={"a": agent_def(model="m", agent_kwargs={"storage": "x"})},
        entry="a",
        session_manager=_file_snapshot(tmp_path),
    )
    with pytest.raises(ConfigurationError, match="storage"):
        load(config)
