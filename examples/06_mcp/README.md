# 06 — MCP: Both Connection Modes

> One example that covers both ways to wire MCP tools to an agent.

## What this shows

| Mode | Key | What it does |
|---|---|---|
| 1 | `command:` | Spawn an MCP server as a stdio subprocess — the client owns it |
| 2 | `url:` | Connect to an MCP server running somewhere else over Streamable HTTP |

Both clients are attached to a **single agent**, which gets calculator tools from
the local subprocess and AWS documentation tools from the remote server.

## How it works

### Mode 1 — stdio subprocess

```yaml
mcp_clients:
  calc_client:
    command: ["python", "calculator_server.py"]
    params:
      prefix: calc                # tools: calc_add, calc_multiply, calc_percentage
```

`calculator_server.py` is an ordinary `FastMCP` script. The MCP client spawns it
on first use and tears it down with the agent, so its whole lifetime is handled
for you.

The subprocess's working directory defaults to the config file's own
directory, so `calculator_server.py` above resolves relative to
`examples/06_mcp/` regardless of where you launch the process from. Set
`transport_options.cwd` explicitly to override it.

This also works with any CLI tool that speaks MCP over stdio — for example
the filesystem server, run on demand via `npx` with no local install:

```yaml
mcp_clients:
  fs_tools:
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    params:
      prefix: fs                  # tools: fs_read_file, fs_list_directory, …
```

### Mode 2 — external HTTP server

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
No API key is needed.

This is the mode to use in production: deploy your MCP server independently
(container, VM, or behind a gateway) and point agents at its URL. To try it
locally, run the example server over HTTP and swap `command:` for `url:`:

```bash
uv run python examples/06_mcp/calculator_server.py --http
```

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

**strands-compose never runs MCP servers.** It creates clients and connects
them. For a local server use `command:` (the client spawns the process); for a
remote one use `url:`.

**No teardown to write.** Strands starts an MCP client when it is attached to an
agent and stops it when the last agent using it goes away.

**`params.prefix`** namespaces all tool names from a client — avoids collisions
when two servers expose identically named tools.

**`params.tool_filters`** limits which tools are visible to the agent — useful
for large servers where you only need a few tools.

**Transport auto-detection.** `url:` clients infer the transport from the URL
path (`/sse` → SSE, otherwise Streamable HTTP). Override with `transport:`.

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
