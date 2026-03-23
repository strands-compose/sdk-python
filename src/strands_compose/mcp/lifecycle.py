"""MCP server and client lifecycle ordering.

Ensures servers are started and ready before clients connect,
and clients are stopped before servers on shutdown.

Key Features:
    - Ordered startup: servers first, then clients
    - Ordered shutdown: clients first, then servers
    - Idempotent start with sync and async context managers
    - Configurable server readiness timeout
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType

    from strands.tools.mcp import MCPClient as StrandsMCPClient

    from .server import MCPServer

logger = logging.getLogger(__name__)


class MCPLifecycle:
    """Manages MCP server and client lifecycle ordering."""

    def __init__(self, server_ready_timeout: float = 30) -> None:
        """Initialize the MCPLifecycle.

        Ensures servers are fully ready before clients connect, and clients
        are stopped before servers on shutdown.

        Example::

            lifecycle = MCPLifecycle()
            lifecycle.add_server("postgres", pg_server)
            lifecycle.add_client("pg_client", pg_client)

            with lifecycle:
                # All servers started and ready, all clients connected
                agent = Agent(tools=[lifecycle.get_client("pg_client")])
                agent("Query the database")

            # All cleaned up

        Or without context manager::

            lifecycle.start()
            try:
                ...
            finally:
                lifecycle.stop()

        Args:
            server_ready_timeout: Seconds to wait for each server to become ready.
        """
        self._servers: dict[str, MCPServer] = {}
        self._clients: dict[str, StrandsMCPClient] = {}
        self._server_ready_timeout = server_ready_timeout
        self._started = False

    def add_server(self, name: str, server: MCPServer) -> None:
        """Register an MCP server.

        Args:
            name: Unique server identifier.
            server: The MCP server instance.

        Raises:
            ValueError: If a server with this name is already registered.
        """
        if name in self._servers:
            raise ValueError(f"MCP server '{name}' is already registered")
        self._servers[name] = server

    def add_client(self, name: str, client: StrandsMCPClient) -> None:
        """Register an MCP client.

        Args:
            name: Unique client identifier.
            client: The strands MCP client instance.

        Raises:
            ValueError: If a client with this name is already registered.
        """
        if name in self._clients:
            raise ValueError(f"MCP client '{name}' is already registered")
        self._clients[name] = client

    def get_server(self, name: str) -> MCPServer:
        """Get a registered server by name.

        Args:
            name: Server identifier.

        Returns:
            The registered MCP server.

        Raises:
            KeyError: If no server with this name is registered.
        """
        if name not in self._servers:
            raise KeyError(f"MCP server '{name}' not registered.\nAvailable: {list(self._servers)}")
        return self._servers[name]

    def get_client(self, name: str) -> StrandsMCPClient:
        """Get a registered client by name.

        Args:
            name: Client identifier.

        Returns:
            The registered strands MCP client.

        Raises:
            KeyError: If no client with this name is registered.
        """
        if name not in self._clients:
            raise KeyError(f"MCP client '{name}' not registered.\nAvailable: {list(self._clients)}")
        return self._clients[name]

    def start(self) -> None:
        """Start all servers and wait for readiness.

        **Idempotent**: if already started, returns immediately.
        ``load()`` calls this before creating agents (so MCP clients can
        connect), and the context manager calls it again on enter — the
        second call is a no-op.  The context manager is still needed for
        **graceful shutdown** via ``stop()``.

        Clients are **not** started here — strands automatically starts
        MCPClient instances when they are registered as tool providers
        on an Agent. Starting them here would cause a "session is currently
        running" error when the Agent tries to start them again.

        Raises:
            RuntimeError: If any server fails to start or become ready.
        """
        if self._started:
            return

        # Phase 1: Start all servers
        for name, server in self._servers.items():
            logger.info("server=<%s> | starting MCP server", name)
            server.start()

        # Phase 2: Wait for all servers to be ready
        for name, server in self._servers.items():
            if not server.wait_ready(timeout=self._server_ready_timeout):
                raise RuntimeError(
                    f"MCP server '{name}' did not become ready within {self._server_ready_timeout}s"
                )
            logger.info("server=<%s> | MCP server is ready", name)

        self._started = True

    def stop(self) -> None:
        """Stop all clients first, then all servers.

        Clients that were never started (e.g., never registered on an Agent)
        are skipped gracefully.
        """
        if not self._started:
            return

        # Phase 1: Stop all clients
        for name, client in self._clients.items():
            try:
                # Normal shutdown — no exception context (matches __exit__ protocol)
                client.stop(exc_type=None, exc_val=None, exc_tb=None)
                logger.info("client=<%s> | MCP client stopped", name)
            except Exception:
                logger.warning("client=<%s> | failed to stop MCP client", name, exc_info=True)

        # Phase 2: Stop all servers
        for name, server in self._servers.items():
            try:
                server.stop()
                logger.info("server=<%s> | MCP server stopped", name)
            except Exception:
                logger.warning("server=<%s> | failed to stop MCP server", name, exc_info=True)

        self._started = False

    def __enter__(self) -> MCPLifecycle:
        """Start lifecycle on context entry."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop lifecycle on context exit."""
        self.stop()

    async def __aenter__(self) -> MCPLifecycle:
        """Async context entry — delegates to sync :meth:`start`.

        Useful with Starlette / ASGI lifespan::

            @asynccontextmanager
            async def lifespan(app):
                async with lifecycle:
                    yield
        """
        self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context exit — delegates to sync :meth:`stop`."""
        self.stop()

    @property
    def servers(self) -> dict[str, MCPServer]:
        """Read-only view of registered servers."""
        return dict(self._servers)

    @property
    def clients(self) -> dict[str, StrandsMCPClient]:
        """Read-only view of registered clients."""
        return dict(self._clients)
