# 12 — Streaming

> Watch every token, tool call, and agent event in real time.

## What this shows

- `wire_event_queue()` — wire all agents to a single async queue that emits `StreamEvent`s
- `AnsiRenderer` — built-in terminal renderer that prints events with colours as they arrive
- How strands-compose turns agent lifecycle events into a consumable stream — the same
  mechanism that powers SSE endpoints, WebSocket feeds, and audit logs

## How it works

```python
from strands_compose import load, AnsiRenderer

resolved = load("config.yaml")
queue = resolved.wire_event_queue()
```

`resolved.wire_event_queue()` installs an `EventPublisher` hook on every agent. As the agent runs,
the hook converts lifecycle events (tokens, tool calls, completions) into `StreamEvent`
objects and pushes them to the queue. Your consumer loop is simple:

```python
renderer = AnsiRenderer()
while (event := await queue.get()) is not None:
    renderer.render(event)
renderer.flush()
```

### Event types

| Type | When it fires |
|------|---------------|
| `agent_start` | Agent begins processing |
| `token` | Streaming text chunk |
| `reasoning` | Streaming reasoning chunk |
| `tool_start` | Tool call begins |
| `tool_end` | Tool call finished |
| `complete` | Agent finished (includes token usage) |
| `node_start` / `node_stop` | Swarm / Graph enters/leaves a node |
| `handoff` | Swarm transfers control |

## Good to know

**This example is async.** Streaming requires `asyncio` — the agent runs via
`invoke_async` so both the agent and the queue consumer share the same event loop.

**`AnsiRenderer` is optional.** It's a convenience for terminals. In production you'd
consume the queue and convert events to SSE chunks (see `OpenAIStreamConverter`) or
NDJSON (`RawStreamConverter`).

**`queue.flush()`** resets the queue between turns so events from one invocation
don't leak into the next.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/12_streaming/main.py
```

## Try these prompts

- `Analyse the impact of large language models on software engineering.`
- `Research current trends in renewable energy adoption.`
- `Examine how remote work has changed urban real-estate markets.`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
