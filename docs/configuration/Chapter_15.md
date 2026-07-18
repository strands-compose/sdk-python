# Chapter 15: Event Streaming — Real-Time Observability

[← Back to Table of Contents](README.md) | [← Previous: Agent Factories](Chapter_14.md)

---

When you have nested orchestrations running, you need visibility into what's happening. `wire_event_queue()` attaches event publishers to every agent and orchestrator and funnels all events into a single async queue.

```python
import asyncio
from strands_compose import AnsiRenderer, load

async def main():
    resolved = load("config.yaml")
    queue = resolved.wire_event_queue()

    async def invoke():
        try:
            await resolved.entry.invoke_async("Analyze LLM trends.")
        finally:
            await queue.close()

    asyncio.create_task(invoke())

    renderer = AnsiRenderer()
    while (event := await queue.get()) is not None:
        renderer.render(event)
    renderer.flush()

asyncio.run(main())
```

## Event Types

Every event is a `StreamEvent` dataclass with four fields: `type`, `agent_name`, `timestamp`, and `data`.

### Session lifecycle events

These two events bracket every invocation. They are produced by the queue layer, not by individual agents.

| Event Type | Description | `data` payload |
|------------|-------------|----------------|
| `SESSION_START` | First event on the queue — emitted before any agent activity | `{"session_id": "<id or null>", "manifest": {SessionManifest}}` — agents, orchestrations, entry point, model info, session manager locations |
| `SESSION_END` | Last typed event before the stream closes | `{"session_id": "<id or null>"}` |

The `SESSION_START` payload wraps the full wired topology snapshot together with the effective session id. Use the `manifest` key to restore conversation history, render an architecture diagram, or audit which models are in use — before any agent has run.

### Per-agent events

| Event Type | Description |
|------------|-------------|
| `AGENT_START` | Agent begins processing |
| `TOKEN` | Individual token streamed from LLM |
| `REASONING` | Reasoning/thinking content from LLM |
| `TOOL_START` | Tool execution begins |
| `TOOL_END` | Tool execution completes |
| `INTERRUPT` | Agent pauses for human input |
| `AGENT_COMPLETE` | Agent finishes — `data` carries `usage` metrics, `model_id`, `provider`, `text` (final output string), and `message` (raw message dict) |
| `ERROR` | Model or execution error |

### Multi-agent events

| Event Type | Description |
|------------|-------------|
| `NODE_START` | Graph/swarm node begins |
| `NODE_STOP` | Graph/swarm node completes |
| `HANDOFF` | Swarm agent hands off to another |
| `MULTIAGENT_START` | Multi-agent orchestration begins |
| `MULTIAGENT_COMPLETE` | Multi-agent orchestration completes |

## AnsiRenderer

The built-in `AnsiRenderer` prints colored terminal output — agent names, tool calls, reasoning traces, tokens — all streaming live. Perfect for development and debugging.

## Custom Event Consumers

Events are `StreamEvent` dataclasses with `.asdict()` for serialization:

```python
while (event := await queue.get()) is not None:
    data = event.asdict()
    # Send to websocket, log to file, push to metrics system...
```

A typical consumer pattern that handles the session lifecycle:

```python
while (event := await queue.get()) is not None:
    if event.type == "session_start":
        session_id = event.data.get("session_id")
        manifest = event.data["manifest"]  # full topology snapshot
        entry = manifest["entry"]          # {"name": "...", "kind": "agent|orchestration"}
    elif event.type == "session_end":
        session_id = event.data.get("session_id")
    else:
        # per-agent or multi-agent event
        process(event)
```

## Configuring the Queue in YAML

Event streaming is configured in Python, not YAML — it's a runtime concern. But the **hooks** it installs (`EventPublisher`) listen to the same lifecycle events as your YAML-defined hooks. They coexist peacefully.

> **Tips & Tricks**
>
> - Call `wire_event_queue()` only **once** per `ResolvedConfig` — it mutates agents and orchestrators by adding hooks. Calling it twice would double-attach publishers.
> - Call `queue.flush()` between requests to clear stale events from a previous invocation. This also resets the `SESSION_START` / `SESSION_END` guards so the next cycle can re-emit them.
> - The queue has a max size of 10,000. If your agent generates more events than the consumer processes, events are dropped with a warning.
> - `SESSION_START` is emitted synchronously by `wire_event_queue()` before any agent runs. `SESSION_END` is emitted by `queue.close()` — always call it in a `finally` block.

---

[Next: Chapter 16 — Name Sanitization →](Chapter_16.md)
