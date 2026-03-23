"""MCP server and client lifecycle management."""

from __future__ import annotations

from strands.tools.mcp import MCPClient

from .client import create_mcp_client
from .lifecycle import MCPLifecycle
from .server import MCPServer, create_mcp_server
from .transports import (
    MCP_SERVER_TRANSPORT,
    sse_transport,
    stdio_transport,
    streamable_http_transport,
)

__all__ = [
    "MCP_SERVER_TRANSPORT",
    "MCPClient",
    "MCPLifecycle",
    "MCPServer",
    "create_mcp_client",
    "create_mcp_server",
    "sse_transport",
    "stdio_transport",
    "streamable_http_transport",
]
