"""Custom MCP server for the 06_mcp example.

Subclass MCPServer and implement _register_tools(mcp) to expose
any Python functions as MCP tools. The create() factory at the
bottom is called by strands-compose with the params from YAML.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from strands_compose.mcp import MCPServer


class CalculatorServer(MCPServer):
    """A simple arithmetic tool server that runs as a background HTTP process."""

    def _register_tools(self, mcp: FastMCP) -> None:
        """Register all tools with the FastMCP instance.

        This method is called once when the server starts.
        Use FastMCP's @mcp.tool() decorator to expose functions.
        """

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


def create(name: str = "calculator", port: int = 9001) -> CalculatorServer:
    """Factory called by strands-compose with params from YAML.

    Args:
        name: Server name assigned by strands-compose (from the YAML key).
        port: The TCP port the MCP server will listen on.

    Returns:
        A configured CalculatorServer instance (not yet started).
    """
    return CalculatorServer(name=name, port=port)
