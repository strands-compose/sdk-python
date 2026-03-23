"""MCP transport factory functions for strands MCPClient.

Each factory returns a callable that produces an MCPTransport (async context manager
yielding (read_stream, write_stream)). Pass the result to strands MCPClient:

    from strands.tools.mcp import MCPClient
    transport = streamable_http_transport("http://localhost:8000/mcp")
    client = MCPClient(transport_callable=transport)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

MCP_TRANSPORT = Literal["stdio", "sse", "streamable-http"]
"""All MCP transport types (client and server)."""

MCP_SERVER_TRANSPORT = Literal["sse", "streamable-http"]
"""Transport types valid for :class:`~strands_compose.mcp.server.MCPServer`.

``stdio`` is excluded because it is a client-side transport where the
client spawns the server as a subprocess and communicates over
stdin/stdout pipes — there is no HTTP server to manage.
"""

DEFAULT_TRANSPORT: MCP_SERVER_TRANSPORT = "streamable-http"


def stdio_transport(
    command: list[str],
    env: dict[str, str] | None = None,
    *,
    cwd: str | Path | None = None,
    encoding: str = "utf-8",
    encoding_error_handler: Literal["strict", "ignore", "replace"] = "strict",
) -> Callable[[], Any]:
    """Create a stdio transport callable for a subprocess MCP server.

    Args:
        command: Command to start the MCP server (e.g., ["python", "-m", "myserver"]).
        env: Optional environment variables for the subprocess.
        cwd: Working directory for the subprocess.
        encoding: Text encoding for messages (default: utf-8).
        encoding_error_handler: How to handle encoding errors (default: strict).

    Returns:
        Transport callable for strands MCPClient.

    Raises:
        ValueError: If command is empty.
    """
    if not command:
        raise ValueError("command must be a non-empty list (e.g., ['python', '-m', 'myserver'])")

    captured_command = list(command)
    captured_env = dict(env) if env is not None else None
    captured_cwd = cwd
    captured_encoding = encoding
    captured_encoding_error_handler = encoding_error_handler

    def factory() -> Any:
        from mcp.client.stdio import StdioServerParameters, stdio_client

        params = StdioServerParameters(
            command=captured_command[0],
            args=captured_command[1:],
            env=captured_env,
            cwd=captured_cwd,
            encoding=captured_encoding,
            encoding_error_handler=captured_encoding_error_handler,
        )
        return stdio_client(params)

    return factory


def sse_transport(
    url: str,
    headers: dict[str, Any] | None = None,
    *,
    timeout: float = 5,
    sse_read_timeout: float = 300,
    auth: Any | None = None,
    httpx_client_factory: Any | None = None,
) -> Callable[[], Any]:
    """Create an SSE (Server-Sent Events) transport callable.

    Args:
        url: SSE endpoint URL.
        headers: Optional HTTP headers.
        timeout: HTTP timeout in seconds (default: 5).
        sse_read_timeout: Timeout waiting for SSE events in seconds (default: 300).
        auth: Optional httpx.Auth instance (e.g., OAuth provider).
        httpx_client_factory: Optional factory for creating httpx client.

    Returns:
        Transport callable for strands MCPClient.

    Raises:
        ValueError: If url is empty.
    """
    if not url:
        raise ValueError("url must be a non-empty string")

    captured_headers = headers or {}
    captured_timeout = timeout
    captured_sse_read_timeout = sse_read_timeout
    captured_auth = auth
    captured_httpx_client_factory = httpx_client_factory

    def factory() -> Any:
        from mcp.client.sse import sse_client

        kwargs: dict[str, Any] = {
            "url": url,
            "headers": captured_headers,
            "timeout": captured_timeout,
            "sse_read_timeout": captured_sse_read_timeout,
        }
        if captured_auth is not None:
            kwargs["auth"] = captured_auth
        if captured_httpx_client_factory is not None:
            kwargs["httpx_client_factory"] = captured_httpx_client_factory
        return sse_client(**kwargs)

    return factory


def streamable_http_transport(
    url: str,
    headers: dict[str, str] | None = None,
    *,
    http_client: Any | None = None,
    terminate_on_close: bool = True,
) -> Callable[[], Any]:
    """Create a streamable HTTP transport callable.

    For full control (auth, timeouts, custom TLS, etc.), pass a pre-configured
    ``httpx.AsyncClient`` via ``http_client``. When ``http_client`` is provided,
    ``headers`` is ignored (configure headers on the client directly).

    Args:
        url: HTTP endpoint URL (e.g., "http://localhost:8000/mcp").
        headers: Optional HTTP headers. Ignored when ``http_client`` is provided.
        http_client: Optional pre-configured ``httpx.AsyncClient``.
        terminate_on_close: Send DELETE to close session (default: True).

    Returns:
        Transport callable for strands MCPClient.

    Raises:
        ValueError: If url is empty.
    """
    if not url:
        raise ValueError("url must be a non-empty string")

    captured_headers = dict(headers) if headers else None
    captured_http_client = http_client
    captured_terminate_on_close = terminate_on_close

    def factory() -> Any:
        from mcp.client.streamable_http import streamable_http_client

        if captured_http_client is not None:
            return streamable_http_client(
                url=url,
                http_client=captured_http_client,
                terminate_on_close=captured_terminate_on_close,
            )
        if captured_headers:
            import httpx

            client = httpx.AsyncClient(headers=captured_headers)
            return streamable_http_client(
                url=url,
                http_client=client,
                terminate_on_close=captured_terminate_on_close,
            )
        return streamable_http_client(url=url, terminate_on_close=captured_terminate_on_close)

    return factory
