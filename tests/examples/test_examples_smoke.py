"""Smoke tests for example YAML configs.

Load every example config through ``load()`` without invoking the agents.
These tests patch external runtime dependencies so they stay independent of
live model providers and MCP availability.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from strands import Agent as _RealAgent

from strands_compose.config import ResolvedConfig, load

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"


class _FakeServer:
    def start(self) -> None:
        pass

    def wait_ready(self, timeout: float) -> bool:
        return True

    def stop(self) -> None:
        pass


class _FakeClient:
    def stop(self, exc_type=None, exc_val=None, exc_tb=None) -> None:
        pass


def _noop_agent_init(self, **kwargs) -> None:
    """No-op Agent init that stores just enough state for smoke tests."""
    self._init_kwargs = kwargs
    self.agent_id = kwargs.get("agent_id", kwargs.get("name"))
    self.name = kwargs.get("name")
    self.model = kwargs.get("model")
    self.system_prompt = kwargs.get("system_prompt")
    self.description = kwargs.get("description")
    self.tools = kwargs.get("tools", [])
    self.hooks = kwargs.get("hooks", [])
    self.callback_handler = kwargs.get("callback_handler")
    self.messages = kwargs.get("messages", [])
    self.state = {}
    self.tool_registry = MagicMock()
    self.tool_registry.registry = {}
    self.hook_registry = MagicMock()
    self._session_manager = kwargs.get("session_manager")


def _fake_orchestrations(config, agents, **kwargs):
    return {name: MagicMock(name=f"orchestration:{name}") for name in config.orchestrations}


def _iter_example_load_inputs() -> list[object]:
    params = []
    for example_dir in sorted(
        p for p in EXAMPLES_DIR.iterdir() if p.is_dir() and p.name[:2].isdigit()
    ):
        yaml_files = sorted(
            example_dir.glob("*.y*ml"),
            key=lambda path: (path.name != "base.yaml", path.name),
        )
        if not yaml_files:
            continue
        load_input = yaml_files[0] if len(yaml_files) == 1 else yaml_files
        params.append(pytest.param(load_input, id=example_dir.name))
    return params


@pytest.mark.integration
@pytest.mark.parametrize("config_input", _iter_example_load_inputs())
def test_example_yaml_loads(config_input):
    with (
        patch.object(_RealAgent, "__init__", _noop_agent_init),
        patch(
            "strands_compose.config.resolvers.config.resolve_model",
            lambda model_def: MagicMock(name="model"),
        ),
        patch(
            "strands_compose.config.resolvers.config.resolve_mcp_server",
            lambda *args, **kwargs: _FakeServer(),
        ),
        patch(
            "strands_compose.config.resolvers.config.resolve_mcp_client",
            lambda *args, **kwargs: _FakeClient(),
        ),
        patch(
            "strands_compose.config.loaders.loaders.resolve_orchestrations", _fake_orchestrations
        ),
    ):
        resolved = load(config_input)

    assert isinstance(resolved, ResolvedConfig)
    assert resolved.entry is not None

    resolved.mcp_lifecycle.stop()
