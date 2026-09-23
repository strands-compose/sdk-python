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
            ``httpx2.AsyncClient``), ``terminate_on_close``

        **kwargs: Additional kwargs forwarded to strands MCPClient
            (startup_timeout, tool_filters, prefix, elicitation_callback,
            tasks_config, etc.).

    Returns:
        A strands MCPClient instance.

    Raises:
        ValueError: If connection parameters are ambiguous, or if ``transport``
            is not an HTTP transport while ``url`` is given.
    """
    modes = sum(x is not None for x in [url, command])
    if modes != 1:
        raise ValueError(
            f"Exactly one of url or command must be provided (got {modes}).\n"
            "url=str for an HTTP MCP server, command=list[str] for subprocess stdio."
        )

    from strands.tools.mcp import MCPClient as _MCPClient

    opts = transport_options or {}
    transport_callable: Any

    if url is None:
        # command is guaranteed non-None by the modes == 1 check above.
        transport_callable = stdio_transport(command, **opts)  # ty: ignore
    else:
        # Detect from the URL path when not given explicitly: /sse selects SSE,
        # anything else selects streamable-http (the modern MCP transport).
        effective = transport
        if effective is None:
            path = urlparse(url).path.rstrip("/")
            effective = "sse" if path.endswith("/sse") else "streamable-http"

        if effective == "streamable-http":
            transport_callable = streamable_http_transport(url, **opts)
        elif effective == "sse":
            transport_callable = sse_transport(url, **opts)
        else:
            raise ValueError(
                f"HTTP-based connection requires 'sse' or 'streamable-http' "
                f"transport, got: {effective}.\n"
                "Use command=list[str] for a stdio subprocess server."
            )

    return _MCPClient(transport_callable=transport_callable, **kwargs)
