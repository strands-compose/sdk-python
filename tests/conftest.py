"""Root fixtures — markers plus the strands runtime fake boundary.

Only genuine shared *infrastructure* lives here. Object construction lives in
``factories.py``; fakes live in ``fakes/``.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from tests.fakes import FakeMCPClient, FakeMCPServer, FakeModel


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: full-pipeline tests (load over YAML)")
    config.addinivalue_line("markers", "ollama: requires local Ollama")
    config.addinivalue_line("markers", "bedrock: requires AWS Bedrock")


@pytest.fixture
def fake_runtime() -> Iterator[None]:
    """Swap the strands-facing resolver seams for fakes.

    Patches ``resolve_model`` / ``resolve_mcp_server`` / ``resolve_mcp_client``
    where ``resolve_infra`` uses them, so ``load`` / ``resolve_infra`` build real
    agents and orchestrations with no network and no MCP subprocess.
    """
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch(
                "strands_compose.config.resolvers.config.resolve_model",
                lambda model_def: FakeModel(),
            )
        )
        stack.enter_context(
            patch(
                "strands_compose.config.resolvers.config.resolve_mcp_server",
                lambda *a, **k: FakeMCPServer(),
            )
        )
        stack.enter_context(
            patch(
                "strands_compose.config.resolvers.config.resolve_mcp_client",
                lambda *a, **k: FakeMCPClient(),
            )
        )
        yield
