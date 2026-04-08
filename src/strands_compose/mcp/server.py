"""Abstract MCP server base class.

Subclasses implement :meth:`_register_tools` to add tools on the
underlying ``FastMCP`` instance.  The base handles lifecycle —
start in a background daemon thread, readiness signaling via
``threading.Event``, and graceful shutdown.

Graceful shutdown
-----------------
The server bypasses ``FastMCP.run()`` — which creates a local
``uvicorn.Server`` that is inaccessible after the call — and instead
obtains the Starlette ASGI app via ``FastMCP.streamable_http_app()`` /
``FastMCP.sse_app()``, then creates and manages its own
``uvicorn.Server``.  This gives us access to
``uvicorn.Server.should_exit`` for clean shutdown from any thread.

Only HTTP transports (``streamable-http``, ``sse``) are supported.
``stdio`` is a client-side transport where the client spawns a server
subprocess — there is no server to manage here.

Example::

    class PostgresServer(MCPServer):
        def _register_tools(self, mcp: FastMCP) -> None:
            mcp.tool()(my_query_func)


    server = PostgresServer(name="postgres", port=8001)
    server.start()
    server.wait_ready(timeout=10)
    # ... use server ...
    server.stop()
"""

from __future__ import annotations

import asyncio
import logging
import socket
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .transports import DEFAULT_TRANSPORT, MCP_SERVER_TRANSPORT

if TYPE_CHECKING:
    import uvicorn
    from mcp.server.fastmcp import FastMCP


logger = logging.getLogger(__name__)


class MCPServer(ABC):
    """Abstract base for strands_compose MCP servers."""

    #: Seconds to wait for uvicorn graceful drain after ``should_exit``.
    STOP_TIMEOUT: float = 5
    #: Extra seconds to wait after ``force_exit`` before giving up.
    STOP_FORCE_TIMEOUT: float = 2

    def __init__(
        self,
        *,
        name: str,
        host: str = "127.0.0.1",
        port: int = 8000,
        transport: MCP_SERVER_TRANSPORT = DEFAULT_TRANSPORT,
        server_params: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the MCPServer.

        Subclasses implement ``_register_tools()`` to register tools on the
        ``FastMCP`` instance.  The base class manages background-thread
        lifecycle and readiness signaling.

        Args:
            name: Unique server identifier.
            host: Bind address for the HTTP transport.
            port: Bind port for the HTTP transport.
            transport: MCP server transport type (``streamable-http`` or ``sse``).
            server_params: Extra keyword arguments forwarded to ``FastMCP()``.
        """
        self.name = name
        self.host = host
        self.port = port
        self.transport = transport
        self.server_params = server_params or {}
        self._mcp: FastMCP | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._uvicorn_server: uvicorn.Server | None = None

    # -- properties ------------------------------------------------- #

    @property
    def url(self) -> str:
        """Base URL of this server (for client transport)."""
        return f"http://{self.host}:{self.port}/mcp"

    @property
    def is_running(self) -> bool:
        """True if the server thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    # -- server creation -------------------------------------------- #

    def create_server(self) -> FastMCP:
        """Build the ``FastMCP`` instance and register tools.

        The result is cached — calling twice returns the same instance.
        """
        if self._mcp is not None:
            return self._mcp

        from mcp.server.fastmcp import FastMCP as _FastMCP

        mcp = _FastMCP(
            self.name,
            host=self.host,
            port=self.port,
            stateless_http=True,
            json_response=True,
            log_level="WARNING",
            **self.server_params,
        )
        self._register_tools(mcp)
        self._mcp = mcp
        return mcp

    # -- lifecycle -------------------------------------------------- #

    def _get_asgi_app(self, mcp: FastMCP) -> Any:
        """Return the Starlette ASGI app for the current transport.

        Calls the corresponding public method on ``FastMCP`` which lazily
        initialises the session manager and returns a ``Starlette``
        instance.

        Raises:
            ValueError: If the transport type is not supported.
        """
        if self.transport == "streamable-http":
            return mcp.streamable_http_app()
        if self.transport == "sse":
            return mcp.sse_app()
        raise ValueError(
            f"Unsupported server transport: {self.transport!r}. "
            "MCPServer only supports 'streamable-http' and 'sse'. "
            "The 'stdio' transport is a client-side transport where the client "
            "spawns the server as a subprocess."
        )

    def run(self) -> None:
        """Start the server blocking (for standalone CLI usage).

        In the main thread ``FastMCP.run()`` installs signal handlers so
        that Ctrl-C triggers a graceful uvicorn shutdown.
        """
        mcp = self.create_server()
        mcp.run(transport=self.transport)

    def start(self) -> None:
        """Start the server in a background daemon thread.

        Creates its own ``uvicorn.Server`` instead of delegating to
        ``FastMCP.run()``.  This keeps a reference to the server so that
        :meth:`stop` can trigger a graceful shutdown via
        ``uvicorn.Server.should_exit``.
        """
        if self.is_running:
            return
        self._ready.clear()
        self._error = None

        mcp = self.create_server()
        asgi_app = self._get_asgi_app(mcp)

        import uvicorn as _uvicorn

        config = _uvicorn.Config(
            asgi_app,
            host=self.host,
            port=self.port,
            log_level="warning",
        )
        self._uvicorn_server = _uvicorn.Server(config)

        def _target() -> None:
            try:
                asyncio.run(self._uvicorn_server.serve())  # ty: ignore
            except BaseException as exc:
                self._error = exc
                self._ready.set()

        self._thread = threading.Thread(
            target=_target,
            name=f"mcp-{self.name}",
            daemon=True,
        )
        self._thread.start()

    def wait_ready(self, timeout: float = 30) -> bool:
        """Wait for the server to be ready by polling the TCP port.

        Returns:
            True if server is ready, False if timed out.

        Raises:
            RuntimeError: If the server thread died before becoming ready.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._error is not None:
                raise RuntimeError(
                    f"MCP server '{self.name}' failed to start: {self._error}"
                ) from self._error
            if self._thread is not None and not self._thread.is_alive():
                raise RuntimeError(f"MCP server '{self.name}' thread exited unexpectedly")
            try:
                with socket.create_connection((self.host, self.port), timeout=1):
                    self._ready.set()
                    return True
            except OSError:
                time.sleep(0.1)
        return False

    def stop(self) -> None:
        """Stop the server and clean up the background thread.

        Signals ``uvicorn.Server.should_exit`` which triggers a graceful
        drain (stop accepting new connections, finish in-flight requests).
        If the thread does not exit within :attr:`STOP_TIMEOUT` seconds,
        ``force_exit`` is set to skip connection draining.  After a
        further :attr:`STOP_FORCE_TIMEOUT` seconds the thread is
        abandoned as a daemon thread and will be reaped when the process
        exits.
        """
        if self._thread is not None and self._thread.is_alive():
            if self._uvicorn_server is not None:
                # Graceful phase: ask uvicorn to stop accepting and drain.
                self._uvicorn_server.should_exit = True
                self._thread.join(timeout=self.STOP_TIMEOUT)

                if self._thread.is_alive():
                    # Forceful phase: skip connection draining.
                    logger.info(
                        "server=<%s>, timeout=<%s> | forcing exit after graceful stop timeout",
                        self.name,
                        self.STOP_TIMEOUT,
                    )
                    self._uvicorn_server.force_exit = True
                    self._thread.join(timeout=self.STOP_FORCE_TIMEOUT)

            if self._thread.is_alive():
                logger.warning(
                    "server=<%s> | thread did not stop, daemon will be reaped at exit", self.name
                )

        self._uvicorn_server = None
        self._mcp = None
        self._thread = None
        self._ready.clear()

    # -- extension point -------------------------------------------- #

    @abstractmethod
    def _register_tools(self, mcp: FastMCP) -> None:
        """Register tools, routes, and resources on the FastMCP instance."""
        ...


def create_mcp_server(
    *,
    name: str,
    tools: list[Callable[..., Any]],
    host: str = "127.0.0.1",
    port: int = 8000,
    transport: MCP_SERVER_TRANSPORT = DEFAULT_TRANSPORT,
    server_params: dict[str, Any] | None = None,
) -> MCPServer:
    """Create an MCP server from a list of callables — no subclassing needed.

    Each callable (sync or async) is registered as a tool on the underlying
    ``FastMCP`` instance.  For advanced use (custom state, routes, resources),
    subclass :class:`MCPServer` directly.

    Example::

        def get_weather(city: str) -> str:
            return f"Sunny in {city}"


        async def query_db(sql: str) -> str: ...


        server = create_mcp_server(name="weather", tools=[get_weather, query_db], port=8001)
        server.start()

    Args:
        name: Unique server identifier.
        tools: Callables to register as MCP tools.
        host: Bind address (default ``127.0.0.1``).
        port: Bind port (default ``8000``).
        transport: Server transport type (``streamable-http`` or ``sse``).
        server_params: Extra kwargs forwarded to ``FastMCP()``.

    Returns:
        A ready-to-use :class:`MCPServer` instance.
    """
    tool_fns = list(tools)

    class _FactoryServer(MCPServer):
        def _register_tools(self, mcp: FastMCP) -> None:
            for fn in tool_fns:
                mcp.tool()(fn)

    return _FactoryServer(
        name=name,
        host=host,
        port=port,
        transport=transport,
        server_params=server_params,
    )
