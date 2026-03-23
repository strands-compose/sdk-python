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

| Event Type | Description |
|------------|-------------|
| `AGENT_START` | Agent begins processing |
| `TOKEN` | Individual token streamed from LLM |
| `REASONING` | Reasoning/thinking content from LLM |
| `TOOL_START` | Tool execution begins |
| `TOOL_END` | Tool execution completes |
| `COMPLETE` | Agent finishes (with usage metrics) |
| `ERROR` | Model or execution error |
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

## Configuring the Queue in YAML

Event streaming is configured in Python, not YAML — it's a runtime concern. But the **hooks** it installs (`EventPublisher`) listen to the same lifecycle events as your YAML-defined hooks. They coexist peacefully.

> **Tips & Tricks**
>
> - Call `wire_event_queue()` only **once** per `ResolvedConfig` — it mutates the agents by adding hooks.
> - Call `queue.flush()` between requests to clear stale events from a previous invocation.
> - The queue has a max size of 10,000. If your agent generates more events than the consumer processes, events are dropped with a warning.

---

[Next: Chapter 16 — Name Sanitization →](Chapter_16.md)
