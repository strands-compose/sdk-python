"""A standalone MCP server for the 06_mcp example.

This is a plain ``FastMCP`` server.
The config launches it as a stdio subprocess via ``command:``, so you never
start it by hand.

To run it directly over HTTP instead (and connect with ``url:``)::

    uv run python examples/06_mcp/calculator_server.py --http
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calculator")


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together.

    Args:
        a: The first operand.
        b: The second operand.

    Returns:
        The sum of a and b.
    """
    return a + b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers together.

    Args:
        a: The first factor.
        b: The second factor.

    Returns:
        The product of a and b.
    """
    return a * b


@mcp.tool()
def percentage(value: float, percent: float) -> float:
    """Calculate what percent% of value is.

    Args:
        value: The base value.
        percent: The percentage to calculate (e.g. 30 means 30%).

    Returns:
        The result of value * percent / 100.
    """
    return value * percent / 100


if __name__ == "__main__":
    # stdio is the default: the MCP client spawns this file as a subprocess.
    # --http serves over Streamable HTTP for use with a url: client instead.
    mcp.run(transport="streamable-http" if "--http" in sys.argv else "stdio")
