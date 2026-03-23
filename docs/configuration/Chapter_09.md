# Chapter 9: MCP — External Tool Servers

[← Back to Table of Contents](README.md) | [← Previous: Conversation Managers](Chapter_08.md)

---

The Model Context Protocol (MCP) lets agents connect to external tool servers. strands-compose supports three connection modes and manages the full server lifecycle.

## Architecture

```
mcp_servers:  → Define managed local servers (strands-compose starts/stops them)
mcp_clients:  → Define connections to servers (local, remote, or subprocess)
agents:
  my_agent:
    mcp: [client_name]  → Attach MCP clients as tool providers
```

## Mode 1: Managed Local Server

You define a server, strands-compose starts it in a background thread before creating agents, and stops it on shutdown:

```yaml
mcp_servers:
  calculator:
    type: ./server.py:create
    params:
      port: 9001

mcp_clients:
  calc:
    server: calculator                # References the server above
    params:
      prefix: calc                    # Tools become calc_add, calc_multiply, etc.

agents:
  assistant:
    mcp: [calc]
    system_prompt: "Use calc tools for math."

entry: assistant
```

The `type` field points to a factory function that returns an `MCPServer` instance:

```python
# server.py
from mcp.server.fastmcp import FastMCP
from strands_compose.mcp import MCPServer

class CalculatorServer(MCPServer):
    def _register_tools(self, mcp: FastMCP) -> None:
        @mcp.tool()
        def add(a: float, b: float) -> float:
            """Add two numbers."""
            return a + b

        @mcp.tool()
        def multiply(a: float, b: float) -> float:
            """Multiply two numbers."""
            return a * b

def create(name: str, port: int = 9001) -> CalculatorServer:
    return CalculatorServer(name=name, port=port)
```

The factory receives `name` (from the YAML key) plus everything in `params`.

## Mode 2: Remote URL

Connect to an existing MCP server over HTTP — no server management needed:

```yaml
mcp_clients:
  aws_docs:
    url: https://knowledge-mcp.global.api.aws
    transport: streamable-http
    params:
      prefix: aws
      startup_timeout: 30
```

## Mode 3: Stdio Subprocess

Spawn a local process that speaks MCP over stdin/stdout:

```yaml
mcp_clients:
  filesystem:
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    params:
      prefix: fs
```

## The `transport` Field

Transport auto-detection usually works, but you can override it:

| Transport | When to Use |
|-----------|-------------|
| `streamable-http` | Default for URLs and managed servers. Modern MCP transport. |
| `sse` | Older Server-Sent Events transport. Auto-detected if URL ends in `/sse`. |
| `stdio` | Set automatically for `command:` mode. Not valid for managed servers. |

## Client `params`

The `params` dict on an MCP client is forwarded to strands' `MCPClient` constructor:

| Param | Type | What It Does |
|-------|------|-------------|
| `prefix` | string | Prefix all tool names from this server (e.g., `calc_add`) |
| `startup_timeout` | number | Seconds to wait for the server to respond |
| `tool_filters` | list | Filter which tools to expose |

## Client `transport_options`

Transport-specific options forwarded to the transport factory:

```yaml
mcp_clients:
  authenticated_server:
    url: https://internal.example.com/mcp
    transport_options:
      headers:
        Authorization: "Bearer ${API_TOKEN}"
```

Available options vary by transport:

- **stdio**: `env`, `cwd`, `encoding`
- **sse**: `headers`, `timeout`, `sse_read_timeout`
- **streamable-http**: `headers`, `http_client`, `terminate_on_close`

## Lifecycle Management

strands-compose handles the startup ordering automatically:

1. Start all MCP **servers** (in parallel)
2. Wait for all servers to be **ready** (TCP port check with configurable timeout)
3. Create agents (which auto-start MCP **clients**)

On shutdown (via context manager or `.stop()`):

1. Stop all **clients** first
2. Then stop all **servers**

Always use the MCP lifecycle context manager:

```python
resolved = load("config.yaml")

with resolved.mcp_lifecycle:
    result = resolved.entry("Hello!")
```

Or for async contexts:

```python
async with resolved.mcp_lifecycle:
    result = await resolved.entry.invoke_async("Hello!")
```

## MCPClientDef Validation

Exactly **one** of `server`, `url`, or `command` must be set on each client. Setting zero or more than one raises a validation error:

```
MCPClientDef requires exactly one of 'server', 'url', or 'command'; got none.
```

## Combining Multiple MCP Sources

A single agent can use tools from multiple MCP clients:

```yaml
agents:
  super_agent:
    mcp:
      - calc_client
      - aws_knowledge
      - filesystem
    system_prompt: "You have math, AWS docs, and filesystem access."
```

> **Tips & Tricks**
>
> - The `prefix` parameter is your friend. It namespaces tools to avoid collisions: `calc_add` vs `aws_add`.
> - For development, managed servers (Mode 1) are the most convenient — everything starts and stops with your script.
> - For production, prefer remote URLs (Mode 2) — deploy MCP servers independently and connect agents to them.
> - Server transport defaults to `streamable-http`. You can also use `sse` for older MCP servers.
> - MCP servers support `server_params` which are forwarded to FastMCP constructor — useful for `stateless_http`, `json_response`, etc.

---

[Next: Chapter 10 — Orchestrations →](Chapter_10.md)
