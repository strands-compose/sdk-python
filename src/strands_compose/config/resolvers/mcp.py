"""Resolve MCPClientDef and tool specs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ...mcp.client import create_mcp_client
from ...mcp.transports import MCP_TRANSPORT
from ...tools import resolve_tool_specs

if TYPE_CHECKING:
    from strands.tools.mcp import MCPClient as StrandsMCPClient

    from ..schema import MCPClientDef


def resolve_tools(tool_specs: list[str]) -> list[Any]:
    """Resolve tool specification strings to tool objects.

    Understands module paths, file paths, and directory paths.

    Args:
        tool_specs: List of tool specification strings.

    Returns:
        Flat list of tool objects.
    """
    return resolve_tool_specs(tool_specs)


def resolve_mcp_client(client_def: MCPClientDef) -> StrandsMCPClient:
    """Resolve an MCPClientDef to a strands MCPClient.

    Args:
        client_def: MCP client definition from YAML.

    Returns:
        A strands MCPClient instance (not started — strands starts it when
        the client is registered as a tool provider on an agent).

    Raises:
        ValueError: If the connection parameters are ambiguous.
    """
    # transport stays None when the YAML omits it, so create_mcp_client can
    # detect it from the URL path instead of being forced to a default.
    transport = cast(MCP_TRANSPORT, client_def.transport) if client_def.transport else None
    return create_mcp_client(
        url=client_def.url,
        command=client_def.command,
        transport=transport,
        transport_options=client_def.transport_options or None,
        **client_def.params,
    )
