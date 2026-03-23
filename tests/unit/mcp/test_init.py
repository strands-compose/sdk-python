"""Tests for core.mcp.__init__ — explicit imports."""

from __future__ import annotations

import pytest


class TestExplicitImports:
    @pytest.mark.parametrize(
        "name",
        [
            "MCPLifecycle",
            "create_mcp_client",
            "MCPServer",
            "sse_transport",
            "stdio_transport",
            "streamable_http_transport",
        ],
    )
    def test_public_symbols_importable(self, name: str) -> None:
        """All public symbols are importable from strands_compose.mcp."""
        import strands_compose.mcp as mcp

        assert hasattr(mcp, name), f"{name!r} not importable"
        obj = getattr(mcp, name)
        assert obj is not None

    def test_unknown_attr_raises(self):
        import strands_compose.mcp as mcp

        with pytest.raises(AttributeError):
            getattr(mcp, "nonexistent_symbol")
