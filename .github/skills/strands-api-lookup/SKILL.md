---
name: strands-api-lookup
description: Look up strands-agents APIs before implementing. Use this when working with strands Agent, hooks, MCP, sessions, multi-agent orchestration, or tool registry.
---

# Strands API Lookup

Before implementing anything, check whether strands-agents already provides it. This project is a **thin wrapper** — reimplementing upstream functionality is a rule violation.

## Key APIs — Do NOT Reimplement

| What | Import | Purpose |
|------|--------|---------|
| `Agent` | `strands.agent.agent` | Core agent class |
| Hook events | `strands.hooks.events` | `BeforeInvocationEvent`, `AfterInvocationEvent`, `BeforeModelCallEvent`, `AfterModelCallEvent`, `BeforeToolCallEvent`, `AfterToolCallEvent` |
| `HookProvider` | `strands.hooks` | Implement `register_hooks(registry)` |
| `MCPClient` | `strands.tools.mcp.mcp_client` | MCP tool client |
| `SessionManager` | `strands.session` | `FileSessionManager`, `S3SessionManager` |
| Multi-agent | `strands.multiagent` | `Swarm`, `Graph` |
| `ToolRegistry` | `strands.tools.registry` | Tool registration |
| `@tool` decorator | `strands.tools.decorator` | Decorator-based tool definition |

## strands-compose Public API

Always import from the **top-level** `strands_compose` package — never from submodules:

```python
# Good — top-level public API
from strands_compose import load, load_config, resolve_infra, load_session
from strands_compose import AppConfig, ResolvedConfig, ResolvedInfra
from strands_compose import EventQueue, StreamEvent

# Bad — reaching into submodules
from strands_compose.config.loaders import load_config      # DON'T
from strands_compose.config.resolvers import resolve_infra   # DON'T
```

## How to Check

1. Search the strands public API:

```bash
uv run python -c "import strands; print(dir(strands))"
```

2. Check the strands Agent API:

```bash
uv run python -c "from strands import Agent; help(Agent)"
```

3. Search the installed strands package directly:

```bash
find .venv/lib/python*/site-packages/strands/ -name "*.py" | head -30
grep -r "def function_name" .venv/lib/python*/site-packages/strands/
```

4. If the functionality exists upstream, import and use it directly.
5. If it does not exist, implement it in this project following `AGENTS.md` rules.
