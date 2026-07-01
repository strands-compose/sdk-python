"""MCPServerDef / MCPClientDef resolution — result-type validation and ref checks."""

from __future__ import annotations

import pytest

from strands_compose.config.resolvers.mcp import resolve_mcp_client, resolve_mcp_server
from strands_compose.config.schema import MCPClientDef, MCPServerDef


def test_server_factory_returning_non_server_raises_type_error():
    # builtins:dict is importable and returns a dict, not an MCPServer.
    with pytest.raises(TypeError):
        resolve_mcp_server(MCPServerDef(type="builtins:dict"), name="s")


def test_client_referencing_unknown_server_raises_value_error():
    with pytest.raises(ValueError, match="phantom"):
        resolve_mcp_client(MCPClientDef(server="phantom"), servers={}, name="c")
