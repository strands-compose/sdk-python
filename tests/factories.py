"""Test-data builders — construct ``*Def`` models and YAML with sane defaults.

Builders keep each test's *relevant* inputs visible and hide the rest. Prefer
these over fixture sprawl; override only the fields the test cares about.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from strands_compose.config.schema import (
    AgentDef,
    AppConfig,
    DelegateConnectionDef,
    DelegateOrchestrationDef,
    GraphEdgeDef,
    GraphOrchestrationDef,
    ModelDef,
    SwarmOrchestrationDef,
)


def model_def(**overrides: Any) -> ModelDef:
    """A valid ModelDef (bedrock by default). Override provider/model_id/params."""
    defaults: dict[str, Any] = {"provider": "bedrock", "model_id": "test-model"}
    return ModelDef(**{**defaults, **overrides})


def agent_def(**overrides: Any) -> AgentDef:
    """A minimal valid AgentDef. Override any agent field."""
    defaults: dict[str, Any] = {"system_prompt": "You are a test agent."}
    return AgentDef(**{**defaults, **overrides})


def app_config(**overrides: Any) -> AppConfig:
    """A minimal valid AppConfig: one agent named ``a`` set as entry.

    Override ``agents``/``entry``/``models``/``orchestrations`` etc. as needed.
    """
    agents = overrides.pop("agents", {"a": agent_def()})
    entry = overrides.pop("entry", "a")
    return AppConfig(agents=agents, entry=entry, **overrides)


def delegate_orchestration(
    entry_name: str, targets: dict[str, str], **overrides: Any
) -> DelegateOrchestrationDef:
    """Build a delegate orchestration from ``{agent_name: description}`` targets."""
    connections = [
        DelegateConnectionDef(agent=name, description=desc) for name, desc in targets.items()
    ]
    return DelegateOrchestrationDef(entry_name=entry_name, connections=connections, **overrides)


def swarm_orchestration(
    entry_name: str, agents: list[str], **overrides: Any
) -> SwarmOrchestrationDef:
    """Build a swarm orchestration over the given agent names."""
    return SwarmOrchestrationDef(entry_name=entry_name, agents=agents, **overrides)


def graph_orchestration(
    entry_name: str, edges: list[tuple[str, str]], **overrides: Any
) -> GraphOrchestrationDef:
    """Build a graph orchestration from ``(from, to)`` edge tuples."""
    edge_defs = [GraphEdgeDef(from_agent=a, to_agent=b) for a, b in edges]
    return GraphOrchestrationDef(entry_name=entry_name, edges=edge_defs, **overrides)


def yaml_config(body: str) -> str:
    """Dedent a YAML literal for parse/pipeline tests."""
    return textwrap.dedent(body)


def write_config(tmp_path: Path, body: str, *, name: str = "config.yaml") -> Path:
    """Write a dedented YAML config to ``tmp_path`` and return its path."""
    path = tmp_path / name
    path.write_text(yaml_config(body))
    return path
