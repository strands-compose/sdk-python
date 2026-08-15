"""MCP client construction and transports. Clients only — never a server."""

from __future__ import annotations

from strands.tools.mcp import MCPClient

from .client import create_mcp_client
from .transports import (
    MCP_TRANSPORT,
    sse_transport,
    stdio_transport,
    streamable_http_transport,
)

__all__ = [
    "MCP_TRANSPORT",
    "MCPClient",
    "create_mcp_client",
    "sse_transport",
    "stdio_transport",
    "streamable_http_transport",
]
