"""Create strands MCPClient instances from configuration.

Returns the standard strands MCPClient (which is a ToolProvider).
No wrapping — full strands functionality is available.

Clients are not started here: strands starts an ``MCPClient`` when it is
registered as a tool provider on an ``Agent``, and stops it again when the
last consuming agent is torn down.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from .transports import (
    MCP_TRANSPORT,
    sse_transport,
    stdio_transport,
    streamable_http_transport,
)

if TYPE_CHECKING:
    from strands.tools.mcp import MCPClient


def create_mcp_client(
    *,
    url: str | None = None,
    command: list[str] | None = None,
    transport: MCP_TRANSPORT | None = None,
    transport_options: dict[str, Any] | None = None,
    **kwargs: Any,
) -> MCPClient:
    """Create a strands MCPClient from connection configuration.

    Exactly one of ``url`` or ``command`` must be provided.

    Args:
        url: MCP server URL (for SSE or streamable-http).
        command: Command to start an MCP server subprocess (stdio transport).
        transport: Override transport type ("stdio", "sse", "streamable-http").
            Leave ``None`` to detect it from the URL path — ``/sse`` selects
            SSE, anything else selects streamable-http.
        transport_options: Extra kwargs forwarded to the transport factory.
            These are transport-specific — see each transport function for
            available options:

            **stdio**: ``env``, ``cwd``, ``encoding``, ``encoding_error_handler``

            **sse**: ``headers``, ``timeout``, ``sse_read_timeout``, ``auth``,
            ``httpx_client_factory``

            **streamable-http**: ``headers``, ``http_client`` (pre-configured
            ``httpx.AsyncClient``), ``terminate_on_close``

        **kwargs: Additional kwargs forwarded to strands MCPClient
            (startup_timeout, tool_filters, prefix, elicitation_callback,
            tasks_config, etc.).

    Returns:
        A strands MCPClient instance.

    Raises:
        ValueError: If connection parameters are ambiguous.
    """
    modes = sum(x is not None for x in [url, command])
    if modes != 1:
        raise ValueError(
            f"Exactly one of url or command must be provided (got {modes}).\n"
            "url=str for an HTTP MCP server, command=list[str] for subprocess stdio."
        )

    opts = transport_options or {}

    if url is not None:
        transport_callable = _transport_for_http(url, transport, opts)
    else:
        # command is guaranteed non-None by the modes == 1 check above.
        transport_callable = stdio_transport(command, **opts)  # ty: ignore

    return _make_strands_client(transport_callable=transport_callable, **kwargs)


def _make_strands_client(**kwargs: Any) -> MCPClient:
    """Create a strands MCPClient instance.

    Args:
        **kwargs: Arguments forwarded to strands MCPClient constructor.

    Returns:
        A strands MCPClient instance.
    """
    from strands.tools.mcp import MCPClient as _MCPClient

    return _MCPClient(**kwargs)


def _transport_for_http(
    url: str,
    transport: MCP_TRANSPORT | None,
    opts: dict[str, Any] | None = None,
) -> Any:
    """Build a transport callable for an HTTP-based MCP connection.

    Args:
        url: The MCP server URL.
        transport: Explicit transport override, or ``None`` to detect it from
            the URL path.
        opts: Transport-specific options forwarded to the transport factory.

    Returns:
        A transport callable for strands MCPClient.

    Raises:
        ValueError: If the transport type is unsupported for an HTTP URL.
    """
    opts = opts or {}
    effective = transport or _detect_transport(url)
    if effective == "streamable-http":
        return streamable_http_transport(url, **opts)
    if effective == "sse":
        return sse_transport(url, **opts)
    raise ValueError(
        f"HTTP-based connection requires 'sse' or 'streamable-http' transport, got: {effective}.\n"
        "Use command=list[str] for a stdio subprocess server."
    )


def _detect_transport(url: str) -> str:
    """Auto-detect transport type from URL.

    Default: streamable-http (the modern MCP transport).

    Args:
        url: The MCP server URL.

    Returns:
        The detected transport type string.
    """
    path = urlparse(url).path.rstrip("/")
    if path.endswith("/sse") or path == "/sse":
        return "sse"
    return "streamable-http"
