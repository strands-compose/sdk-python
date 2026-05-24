# 12 — Streaming

> Watch every token, tool call, and agent event in real time.

## What this shows

- `wire_event_queue()` — wire all agents and orchestrators to a single async queue that emits `StreamEvent`s
- `AnsiRenderer` — built-in terminal renderer that prints events with colours as they arrive
- How strands-compose turns agent lifecycle events into a consumable stream — the same
  mechanism that powers SSE endpoints, WebSocket feeds, and audit logs

## How it works

```python
from strands_compose import load, AnsiRenderer

resolved = load("config.yaml")
queue = resolved.wire_event_queue()
```

`resolved.wire_event_queue()` installs an `EventPublisher` hook on every agent and orchestrator.
As the session runs, hooks convert lifecycle events (tokens, tool calls, completions) into
`StreamEvent` objects and push them to the queue. Your consumer loop is simple:

```python
renderer = AnsiRenderer()
while (event := await queue.get()) is not None:
    renderer.render(event)
renderer.flush()
```

### Event types

Every invocation produces a `SESSION_START` as the first event and `SESSION_END` as the last,
bracketing all per-agent activity.

| Type | When it fires | `data` |
|------|---------------|--------|
| `session_start` | Before any agent runs — first event on the queue | Serialised `SessionManifest` (agents, orchestrations, entry, model info) |
| `agent_start` | Agent begins processing | — |
| `token` | Streaming text chunk | `{"text": "..."}` |
| `reasoning` | Streaming reasoning chunk | `{"text": "..."}` |
| `tool_start` | Tool call begins | tool name, input |
| `tool_end` | Tool call finished | tool name, status, result |
| `interrupt` | Agent pauses for human input | interrupt id, reason |
| `complete` | Agent finished (includes token usage) | usage metrics |
| `error` | Model or execution error | exception type, message |
| `node_start` / `node_stop` | Swarm / Graph enters/leaves a node | node id |
| `handoff` | Swarm transfers control | from/to node ids |
| `multiagent_start` | Multi-agent orchestration begins | — |
| `multiagent_complete` | Multi-agent orchestration completes | — |
| `session_end` | After all agent events — last typed event | `{"session_id": "<id or null>"}` |

## Good to know

**This example is async.** Streaming requires `asyncio` — the agent runs via
`invoke_async` so both the agent and the queue consumer share the same event loop.

**`AnsiRenderer` is optional.** It's a convenience for terminals. In production you'd
consume the queue and convert events to SSE chunks (see `OpenAIStreamConverter`) or
NDJSON (`RawStreamConverter`).

**`queue.flush()`** resets the queue between turns so events from one invocation
don't leak into the next. It also resets the `session_start` / `session_end` guards.

**`queue.close()`** emits `session_end` then signals end-of-stream. Always call it in
a `finally` block so `session_end` is guaranteed even when an exception occurs.

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
