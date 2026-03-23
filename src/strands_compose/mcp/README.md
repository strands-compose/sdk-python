# MCP Module — Developer Guide

This module manages the full lifecycle of [Model Context Protocol](https://modelcontextprotocol.io/) servers and clients within strands-compose.  It bridges the gap between the low-level `mcp` Python SDK (which provides `FastMCP` and transport primitives) and the strands agent framework (which consumes `MCPClient` as a tool provider).

The compose config layer resolves YAML declarations into the objects defined here; this module knows nothing about YAML — it only deals with constructed Python objects and their lifecycle.

---

## server — `MCPServer` and `create_mcp_server`

**Responsibility:** Define, build, start, and **gracefully stop** MCP tool servers.

`MCPServer` is an abstract base class.  Subclasses implement `_register_tools(mcp)` to register tool functions, custom routes, or resources on the underlying `FastMCP` instance.  Everything else — thread management, readiness probing, and shutdown — is handled by the base.

`create_mcp_server(name, tools=[...])` is a convenience factory that creates an `MCPServer` without subclassing.  It's used by YAML configs that list plain callables.

### Why we bypass `FastMCP.run()`

`FastMCP.run(transport="streamable-http")` internally does:

```python
async def run_streamable_http_async(self):
    config = uvicorn.Config(self.streamable_http_app(), ...)
    server = uvicorn.Server(config)
    await server.serve()   # blocks forever
```

The `uvicorn.Server` instance is a **local variable** — it is never stored on `self`.  When running in a background thread, uvicorn cannot install signal handlers (Python restricts `signal.signal()` to the main thread), so there is no way to trigger shutdown from outside.

Our solution: call `FastMCP.streamable_http_app()` (or `sse_app()`) ourselves to get the Starlette ASGI app, then create and hold our own `uvicorn.Server`.  This gives us access to `uvicorn.Server.should_exit` — a boolean that uvicorn's main loop polls every 100 ms.  Setting it from any thread triggers graceful shutdown (stop accepting -> drain -> exit).

### Shutdown sequence

`stop()` follows a two-phase escalation:

1. **Graceful** — set `should_exit = True`, wait `STOP_TIMEOUT` (5 s).  Uvicorn stops accepting connections and drains in-flight requests.
2. **Forced** — if still alive, set `force_exit = True`, wait `STOP_FORCE_TIMEOUT` (2 s).  Uvicorn skips connection draining and exits immediately.
3. **Abandoned** — if the thread is still alive, log a warning.  The thread is a daemon and will be reaped at process exit.

### Transport types

Only HTTP transports (`streamable-http`, `sse`) are supported for `MCPServer`.  The type alias `MCP_SERVER_TRANSPORT = Literal["sse", "streamable-http"]` enforces this at the type level.

`stdio` is a **client-side** transport where the client spawns a server subprocess and communicates over stdin/stdout pipes.  There is no HTTP server to manage, so it doesn't belong in `MCPServer`.  Client-side stdio is fully supported via `create_mcp_client(command=...)` and `stdio_transport()`.

### Subclass contract

Subclasses only need to implement `_register_tools(mcp: FastMCP)`.  Override `run()` for blocking-mode customisation (e.g. the Postgres server adds `finally: close_pools()`).  Override `stop()` if you need cleanup after the server thread exits (e.g. closing database pools).

---

## client — `create_mcp_client`

**Responsibility:** Create a strands `MCPClient` from one of three connection modes.

Exactly one of these must be provided:

| Parameter | Transport | Use case |
|-----------|-----------|----------|
| `server=` | streamable-http (default) or sse | Connect to a managed `MCPServer` running in the same process |
| `url=` | Auto-detected from URL path, or explicit override | Connect to an external MCP server |
| `command=` | stdio | Launch a subprocess MCP server |

The function auto-detects transport from URL paths (e.g. `/sse` -> SSE, everything else -> streamable-http).  Transport-specific options (`headers`, `timeout`, `http_client`, etc.) are forwarded via `transport_options`.

The returned object is a standard strands `MCPClient` — no wrapping, full strands functionality.  Strands auto-starts clients when they're registered on an `Agent`, so client start is not managed here.

---

## transports — Transport factory functions

**Responsibility:** Create transport callables that strands `MCPClient` accepts as `transport_callable`.

Each factory captures its configuration in a closure and returns a zero-argument callable that produces an async context manager yielding `(read_stream, write_stream)`.  This deferred construction matters because strands creates the transport connection lazily when the agent first needs tools.

Three factories corresponding to the three MCP transport types:

- **`streamable_http_transport(url, headers=, http_client=)`** — wraps `mcp.client.streamable_http.streamable_http_client`.  Supports pre-configured `httpx.AsyncClient` for custom auth/TLS.
- **`sse_transport(url, headers=, timeout=, auth=)`** — wraps `mcp.client.sse.sse_client`.
- **`stdio_transport(command, env=, cwd=)`** — wraps `mcp.client.stdio.stdio_client`.

---

## lifecycle — `MCPLifecycle`

**Responsibility:** Enforce startup and shutdown ordering across multiple servers and clients.

The ordering constraint is:

1. **Start:** all servers start and become ready (TCP port responds) *before* any client can connect.
2. **Stop:** all clients stop *before* any server stops.

This prevents clients from connecting to servers that aren't ready, and prevents servers from shutting down while clients still have open sessions.

### Integration with compose

The config resolver assembles an `MCPLifecycle` with all declared servers and clients, but does **not** start it.  The `load()` function calls `lifecycle.start()` before creating agents.  Agents auto-start their MCP clients on construction.

Shutdown happens via context manager (`with lifecycle:` / `async with lifecycle:`) or explicit `lifecycle.stop()` in a `finally` block.

### Why clients are not started in `lifecycle.start()`

Strands `MCPClient` manages its own session lifecycle.  It starts automatically when registered on an `Agent`.  If we started clients in `lifecycle.start()`, the `Agent` constructor would fail with "session is currently running".  So `lifecycle.start()` only starts *servers* — clients are left for strands to manage.

`lifecycle.stop()` does stop clients explicitly because strands does not auto-stop them on agent destruction.
