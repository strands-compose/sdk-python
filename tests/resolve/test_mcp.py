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
    "url",
    [
        pytest.param("https://example.com/sse", id="sse-path"),
        pytest.param("https://example.com/sse/", id="sse-path-trailing-slash"),
    ],
)
def test_sse_transport_is_detected_from_the_url_path(url: str):
    # No transport in the YAML — the URL path has to decide on its own.
    with record_chosen_transport() as chosen:
        resolve_mcp_client(MCPClientDef(url=url))

    assert chosen == ["sse"]


def test_plain_streamable_http_url_uses_the_native_strands_client():
    with record_chosen_transport() as chosen:
        client = resolve_mcp_client(MCPClientDef(url="https://example.com/mcp"))

    assert chosen == []
    assert isinstance(client, MCPClient)


def test_explicit_transport_overrides_url_detection():
    with record_chosen_transport() as chosen:
        client = resolve_mcp_client(
            MCPClientDef(url="https://example.com/sse", transport="streamable-http")
        )

    assert chosen == []
    assert isinstance(client, MCPClient)


def test_transport_option_headers_use_the_native_strands_client():
    with record_chosen_transport() as chosen:
        client = resolve_mcp_client(
            MCPClientDef(
                url="https://example.com/mcp",
                transport_options={"headers": {"Authorization": "Bearer t"}},
            )
        )

    assert chosen == []
    assert isinstance(client, MCPClient)


def test_terminate_on_close_option_keeps_the_streamable_http_transport_factory():
    with record_chosen_transport() as chosen:
        resolve_mcp_client(
            MCPClientDef(
                url="https://example.com/mcp", transport_options={"terminate_on_close": False}
            )
        )

    assert chosen == ["streamable-http"]


@pytest.mark.filterwarnings("ignore:Omitting `issuer`")
def test_oauth_client_credentials_resolve_on_a_streamable_http_url():
    client = resolve_mcp_client(
        MCPClientDef(
            url="https://example.com/mcp",
            params={"auth": {"client_id": "id", "client_secret": "secret", "scopes": ["read"]}},
        )
    )

    assert isinstance(client, MCPClient)


def test_auth_with_a_custom_http_client_raises_value_error():
    with pytest.raises(ValueError):
        resolve_mcp_client(
            MCPClientDef(
                url="https://example.com/mcp",
                params={"auth": {"client_id": "id", "client_secret": "secret"}},
                transport_options={"http_client": object()},
            )
        )


def test_headers_in_both_params_and_transport_options_raise_value_error():
    with pytest.raises(ValueError, match="headers"):
        resolve_mcp_client(
            MCPClientDef(
                url="https://example.com/mcp",
                params={"headers": {"X-A": "1"}},
                transport_options={"headers": {"X-B": "2"}},
            )
        )


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
