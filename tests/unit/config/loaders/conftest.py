"""Shared fixtures for config/loaders tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def write_config(tmp_path: Path):
    """Write a YAML config file and return its path.

    Usage::

        def test_something(write_config):
            cfg = write_config("agents:\\n  a:\\n    system_prompt: hi\\nentry: a\\n")
            config = load_config(cfg)
    """

    def _write(content: str, name: str = "config.yaml") -> Path:
        f = tmp_path / name
        f.write_text(content)
        return f

    return _write


def _agent_yaml(name: str = "a", prompt: str = "hi", **extra: Any) -> str:
    """Build a single agent YAML block.

    Args:
        name: Agent name.
        prompt: System prompt text.
        **extra: Additional agent-level keys (e.g. model="m", mcp=["c"]).

    Returns:
        YAML string for one agent entry (without the ``agents:`` header).
    """
    lines = [f"  {name}:", f"    system_prompt: {prompt}"]
    for key, val in extra.items():
        if isinstance(val, list):
            lines.append(f"    {key}:")
            for item in val:
                lines.append(f"      - {item}")
        else:
            lines.append(f"    {key}: {val}")
    return "\n".join(lines)


def _agents_yaml(*agents: str, entry: str | None = None) -> str:
    """Wrap one or more agent blocks into a full YAML config.

    Each argument is the output of :func:`_agent_yaml`.
    ``entry`` defaults to the first agent name.

    Returns:
        Complete YAML config string.
    """
    body = "\n".join(agents)
    if entry is None:
        # Extract the first agent name from the first block
        first_line = agents[0].strip().split("\n")[0]
        entry = first_line.strip().rstrip(":")
    return f"agents:\n{body}\nentry: {entry}\n"


def _minimal_yaml(prompt: str = "hi", entry: str = "a") -> str:
    """Smallest valid config: one agent with a prompt."""
    return f"agents:\n  {entry}:\n    system_prompt: {prompt}\nentry: {entry}\n"


def _swarm_yaml(
    agents: list[str],
    entry_name: str | None = None,
    orch_name: str = "main",
) -> str:
    """Build a swarm orchestration block (no agents section — combine separately)."""
    entry_name = entry_name or agents[0]
    agent_list = "\n".join(f"      - {a}" for a in agents)
    return (
        f"orchestrations:\n"
        f"  {orch_name}:\n"
        f"    mode: swarm\n"
        f"    entry_name: {entry_name}\n"
        f"    agents:\n"
        f"{agent_list}\n"
    )


def _graph_yaml(
    edges: list[tuple[str, str]],
    entry_name: str | None = None,
    orch_name: str = "main",
) -> str:
    """Build a graph orchestration block."""
    entry_name = entry_name or edges[0][0]
    edge_lines = "\n".join(f"      - from: {frm}\n        to: {to}" for frm, to in edges)
    return (
        f"orchestrations:\n"
        f"  {orch_name}:\n"
        f"    mode: graph\n"
        f"    entry_name: {entry_name}\n"
        f"    edges:\n"
        f"{edge_lines}\n"
    )


def _delegate_yaml(
    entry_name: str,
    connections: list[tuple[str, str]],
    orch_name: str = "main",
) -> str:
    """Build a delegate orchestration block.

    Args:
        entry_name: Name of the entry agent.
        connections: ``[(child, description), ...]``.
    """
    lines = [
        "orchestrations:",
        f"  {orch_name}:",
        "    mode: delegate",
        f"    entry_name: {entry_name}",
        "    connections:",
    ]
    for child, desc in connections:
        lines.append(f"      - agent: {child}")
        lines.append(f"        description: {desc}")
    return "\n".join(lines) + "\n"
