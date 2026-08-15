"""MCPClientDef resolution — connection-mode dispatch, transport choice, validation."""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from strands.tools.mcp import MCPClient

from strands_compose.config.resolvers.mcp import resolve_mcp_client
from strands_compose.config.schema import MCPClientDef


def test_url_client_resolves_to_strands_mcp_client():
    client = resolve_mcp_client(MCPClientDef(url="https://example.com/mcp"))

    assert isinstance(client, MCPClient)


@contextlib.contextmanager
def record_chosen_transport() -> Generator[list[str]]:
    """Record which transport factory ``create_mcp_client`` reaches for.

    Which transport a client ends up on is the observable contract here, and the
    two factories are our own seam, so swapping them is the cheapest way to see
    the decision without touching the strands client's internals.
    """
    chosen: list[str] = []

    def _factory(name: str):
        def build(url: str, **kwargs: object):
            chosen.append(name)
            return lambda: None

        return build

    with (
        patch("strands_compose.mcp.client.sse_transport", _factory("sse")),
        patch(
            "strands_compose.mcp.client.streamable_http_transport",
            _factory("streamable-http"),
        ),
    ):
        yield chosen


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        pytest.param("https://example.com/sse", "sse", id="sse-path"),
        pytest.param("https://example.com/sse/", "sse", id="sse-path-trailing-slash"),
        pytest.param("https://example.com/mcp", "streamable-http", id="other-path"),
    ],
)
def test_transport_is_detected_from_the_url_path(url: str, expected: str):
    # No transport in the YAML — the URL path has to decide on its own.
    with record_chosen_transport() as chosen:
        resolve_mcp_client(MCPClientDef(url=url))

    assert chosen == [expected]


def test_explicit_transport_overrides_url_detection():
    with record_chosen_transport() as chosen:
        resolve_mcp_client(MCPClientDef(url="https://example.com/sse", transport="streamable-http"))

    assert chosen == ["streamable-http"]


def test_command_client_resolves_to_strands_mcp_client():
    client = resolve_mcp_client(MCPClientDef(command=["python", "-m", "myserver"]))

    assert isinstance(client, MCPClient)


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({}, id="neither"),
        pytest.param({"url": "https://example.com/mcp", "command": ["x"]}, id="both"),
    ],
)
def test_client_requires_exactly_one_connection_mode(kwargs: dict):
    with pytest.raises(ValidationError):
        MCPClientDef(**kwargs)


def test_stdio_transport_on_a_url_client_raises_value_error():
    with pytest.raises(ValueError, match="stdio"):
        resolve_mcp_client(MCPClientDef(url="https://example.com/mcp", transport="stdio"))
