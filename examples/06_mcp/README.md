# 06 — MCP: All Connection Modes

> One example that covers every way to wire MCP tools to an agent.

## What this shows

| Mode | Key | What it does |
|---|---|---|
| 1 | `server:` | Launch a local Python MCP server; strands-compose owns its full lifecycle |
| 2 | `url:` | Connect to a real external MCP server over Streamable HTTP — no server setup |
| 3 | `command:` *(commented)* | Spawn a local CLI tool that speaks MCP over stdio |

Both live clients are attached to a **single agent**, which gets calculator tools
from the local server and AWS documentation tools from the remote server.

## How it works

### Mode 1 — local managed server

```yaml
mcp_servers:
  calculator:
    type: ./server.py:create      # factory function -> MCPServer subclass
    params:
      port: 9001

mcp_clients:
  calc_client:
    server: calculator            # auto-connects; transport/URL inferred
    params:
      prefix: calc                # tools: calc_add, calc_multiply, calc_percentage
```

`server.py` subclasses `MCPServer` and uses FastMCP's `@mcp.tool()` decorator.
The `create()` factory is called by strands-compose with `params` from YAML.
On `load()`, strands-compose starts the server, connects the client, and on exit
`mcp_lifecycle.stop()` tears everything down — you never manage threads or sockets.

### Mode 2 — real external HTTP server

```yaml
mcp_clients:
  aws_knowledge:
    url: https://knowledge-mcp.global.api.aws
    transport: streamable-http    # auto-detected from URL if omitted
    params:
      prefix: aws                 # tools: aws_search, aws_read_doc, …
      startup_timeout: 30
```

AWS publicly hosts a Knowledge MCP server at `https://knowledge-mcp.global.api.aws`.
No API key is needed. No `mcp_servers:` block — the server is already running.

### Mode 3 — stdio subprocess *(uncomment in config to try)*

```yaml
mcp_clients:
  fs_tools:
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    params:
      prefix: fs
```

For CLI tools that speak MCP over stdin/stdout. Works with any `npx`, `uvx`,
or binary that implements the MCP stdio protocol.

### Attaching both clients to one agent

```yaml
agents:
  assistant:
    mcp:
      - calc_client
      - aws_knowledge
```

The agent sees `calc_*` and `aws_*` tools simultaneously and picks the right one
based on the question.

## Good to know

**`mcp_servers:` is only needed for locally managed servers.** For `url:` or
`command:` clients you connect to servers you don't own — no `mcp_servers:` block.

**`params.prefix`** namespaces all tool names from a client — avoids collisions
when two servers expose identically named tools.

**`params.tool_filters`** limits which tools are visible to the agent — useful
for large servers where you only need a few tools.

**Transport auto-detection.** `url:` clients infer the transport from the URL
scheme and path. Override with `transport:` if needed.

**Paths** in `type:` are relative to the config file, not the working directory.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables) for the Bedrock model
- Dependencies installed: `uv sync`
- No extra credentials needed for the AWS Knowledge MCP endpoint

## Run

```bash
uv run python examples/06_mcp/main.py
```

## Try these prompts

- `What is 15% of 240? Also, what is Amazon S3?`
- `Add 47 and 89, then multiply the result by 3.`
- `What IAM permissions do I need to read objects from an S3 bucket?`
- `I have a budget of 1200. Allocate 35% to marketing. How much is that?`
- `Explain the difference between Amazon RDS and Amazon Aurora.`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
