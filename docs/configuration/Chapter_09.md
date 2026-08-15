# Chapter 9: MCP — External Tool Servers

[← Back to Table of Contents](README.md) | [← Previous: Conversation Managers](Chapter_08.md)

---

The Model Context Protocol (MCP) lets agents connect to external tool servers. strands-compose creates the **clients**; the servers run outside it.

## Architecture

```
mcp_clients:  → Define connections to MCP servers (subprocess or remote)
agents:
  my_agent:
    mcp: [client_name]  → Attach MCP clients as tool providers
```

strands-compose never runs an MCP server. There are two ways to connect:

| Mode | Key | The server is… |
|------|-----|----------------|
| 1 | `command:` | started as a subprocess by the MCP client |
| 2 | `url:` | already running somewhere else |

## Mode 1: Stdio Subprocess

The client spawns the server process and talks to it over stdin/stdout. Nothing to
start by hand, no ports, no readiness checks:

```yaml
mcp_clients:
  calc:
    command: ["python", "-m", "myserver"]
    params:
      prefix: calc                    # Tools become calc_add, calc_multiply, etc.

agents:
  assistant:
    mcp: [calc]
    system_prompt: "Use calc tools for math."

entry: assistant
```

Any MCP server works. A [FastMCP](https://github.com/modelcontextprotocol/python-sdk) script is
the shortest way to write one:

```python
# myserver.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calculator")


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

This mode also works with any CLI tool that speaks MCP over stdio:

```yaml
mcp_clients:
  filesystem:
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    params:
      prefix: fs
```

## Mode 2: Remote URL

Connect to a server you deploy and operate separately — a container, a VM, or
something behind an API gateway:

```yaml
mcp_clients:
  aws_docs:
    url: https://knowledge-mcp.global.api.aws
    transport: streamable-http
    params:
      prefix: aws
      startup_timeout: 30
```

This is the mode to prefer in production. Because the server lives outside your
agent process, one deployment can serve many agents and many sessions, and you
can put authentication, rate limiting, and observability in front of it.

## The `transport` Field

Transport auto-detection usually works, but you can override it:

| Transport | When to Use |
|-----------|-------------|
| `streamable-http` | Default for `url:` clients. Modern MCP transport. |
| `sse` | Older Server-Sent Events transport. Auto-detected if the URL path ends in `/sse`. |
| `stdio` | Set automatically for `command:` mode. Not valid with `url:`. |

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

- **stdio**: `env`, `cwd`, `encoding`, `encoding_error_handler`
- **sse**: `headers`, `timeout`, `sse_read_timeout`, `auth`, `httpx_client_factory`
- **streamable-http**: `headers`, `http_client`, `terminate_on_close`

## Lifecycle

There is nothing to manage. Strands starts an MCP client when it is attached to
an agent, and stops it once the last agent using it is torn down — including the
subprocess in `command:` mode.

```python
resolved = load("config.yaml")
result = resolved.entry("Hello!")
```

Or in an async context:

```python
result = await resolved.entry.invoke_async("Hello!")
```

A short-lived script needs no teardown — the process exits and the subprocess
goes with it. A long-running process that discards sessions should release them
explicitly, since strands only stops a client once every `Agent` holding it is
garbage-collected:

```python
from strands import Agent

for node in (*resolved.agents.values(), *resolved.orchestrators.values()):
    if isinstance(node, Agent):
        node.cleanup()
```

Include the orchestrators — a `delegate` orchestration is an `Agent` forked from
its entry agent, holding the same MCP clients without appearing in `agents`.

To confirm the whole config builds — including every MCP client — before you
ship, run the CLI:

```bash
strands-compose load config.yaml
```

A connection failure surfaces on the first tool call, as a normal agent error.

## MCPClientDef Validation

Exactly **one** of `url` or `command` must be set on each client. Setting neither or both raises a validation error:

```
MCPClientDef requires exactly one of 'url' or 'command'; got none.
```

## Combining Multiple MCP Sources

A single agent can use tools from multiple MCP clients:

```yaml
agents:
  super_agent:
    mcp:
      - calc
      - aws_docs
      - filesystem
    system_prompt: "You have math, AWS docs, and filesystem access."
```

> **Tips & Tricks**
>
> - The `prefix` parameter is your friend. It namespaces tools to avoid collisions: `calc_add` vs `aws_add`.
> - For development, `command:` is the most convenient — the server starts and stops with your agent, and you edit it in the same repo.
> - For production, prefer `url:` — deploy MCP servers independently so a single instance can serve every agent and hold shared resources like database connection pools.
> - Use `tool_filters` to give different agents different slices of the same server.

---

[Next: Chapter 10 — Orchestrations →](Chapter_10.md)
