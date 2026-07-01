"""SessionManagerDef resolution and the uniform leaf-chain precedence."""

from __future__ import annotations

import pytest
from strands.session import FileSessionManager
from strands.session.session_manager import SessionManager

from strands_compose.config import load_session, resolve_infra
from strands_compose.config.resolvers.session_manager import (
    resolve_leaf_session_manager,
    resolve_session_manager,
)
from strands_compose.config.schema import AppConfig, SessionManagerDef
from strands_compose.manifest import build_manifest
from tests.factories import agent_def, model_def


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


# ── Infra/session split — load-level composition ───────────────────────────


def test_global_agentcore_provider_is_rejected_by_resolve_infra():
    # agentcore needs a unique actor_id per agent, so it can't be a global default.
    config = AppConfig(
        agents={"a": agent_def()},
        entry="a",
        session_manager=SessionManagerDef(provider="agentcore"),
    )
    with pytest.raises(ValueError, match="agentcore"):
        resolve_infra(config)


def test_global_session_manager_propagates_to_the_built_entry_agent(tmp_path, fake_runtime):
    config = AppConfig(
        models={"m": model_def()},
        agents={"a": agent_def(model="m")},
        entry="a",
        session_manager=SessionManagerDef(provider="file", params={"storage_dir": str(tmp_path)}),
    )
    resolved = load_session(config, resolve_infra(config), session_id="s1")

    # Observe via the manifest (public introspection), not private agent state.
    manifest = build_manifest(resolved.agents, resolved.orchestrators, resolved.entry)
    assert manifest.agents[0].session_manager is not None
    assert manifest.agents[0].session_manager.provider == "file"


def test_two_sessions_over_one_infra_build_isolated_agents(tmp_path, fake_runtime):
    # The whole point of the split: reuse infra, create fresh agents per session.
    config = AppConfig(
        models={"m": model_def()},
        agents={"a": agent_def(model="m")},
        entry="a",
        session_manager=SessionManagerDef(provider="file", params={"storage_dir": str(tmp_path)}),
    )
    infra = resolve_infra(config)

    r1 = load_session(config, infra, session_id="s1")
    r2 = load_session(config, infra, session_id="s2")

    assert r1.agents["a"] is not r2.agents["a"]
