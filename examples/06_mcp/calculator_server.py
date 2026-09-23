"""A standalone MCP server for the 06_mcp example.

Compatible with mcp>=2.0 (MCPServer replaces FastMCP).
The config launches it as a stdio subprocess via ``command:``, so you never
start it by hand.
"""

from __future__ import annotations

from mcp.server import MCPServer

mcp = MCPServer("calculator")


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
    # The MCP client spawns this file as a stdio subprocess.
    mcp.run(transport="stdio")
