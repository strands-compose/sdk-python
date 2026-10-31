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

The snapshot providers (`file-snapshot`, `s3-snapshot`) are reported as `{"provider": "snapshot", "session_id": "..."}` with no storage location, because strands keeps the storage private. Read the folder or bucket from your config instead.

### Per-agent events

| Event Type | Description |
|------------|-------------|
| `AGENT_START` | Agent begins processing |
| `TOKEN` | Individual token streamed from LLM |
| `REASONING` | Reasoning/thinking content from LLM |
| `TOOL_START` | Tool execution begins |
| `TOOL_END` | Tool execution completes — `data.status` is `error` when the tool raised, was cancelled (by a guard or hook), or returned an error result |
| `INTERRUPT` | Agent pauses for human input |
| `AGENT_COMPLETE` | Agent finishes — `data` carries `usage`, `stop_reason`, `model` (`model_id`, `provider`), `text` (final output string), and `message` (raw message dict) |
| `ERROR` | A model call failed and was not recovered by a retry or failover |

`AGENT_COMPLETE.data.usage` has the keys `input_tokens`, `output_tokens`, `total_tokens`, `cache_read_input_tokens` and `cache_write_input_tokens` (each defaults to 0), counted for this agent's own model calls in the invocation. Values are passed through as the provider reports them. On Bedrock and Anthropic, `input_tokens` excludes the cache counts. `stop_reason` is strands' stop reason, for example `end_turn`, `max_tokens`, or `cancelled` when a guard stopped the run.

### Multi-agent events

| Event Type | Description |
|------------|-------------|
| `NODE_START` | Graph/swarm node begins |
| `NODE_STOP` | Graph/swarm node completes — `data` carries `node_id`, `multiagent_type`, `status` (`completed`, `failed`, ...), `execution_time_ms` and `usage` (same keys as `AGENT_COMPLETE.usage`). The usage is the node's total and overlaps the node agent's own `AGENT_COMPLETE`; do not sum both |
| `HANDOFF` | Swarm only — an agent hands off to another. `data` carries `from_node_ids`, `to_node_ids` and `message`; emitted right after the handing-off node's `NODE_STOP` |
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

`TOKEN` and `REASONING` events have no hook, so `EventPublisher` also registers a model-stream middleware (`InvokeModelStage`) on each agent. It forwards every event unchanged. The first middleware registered is the outermost, so `TOKEN` and `REASONING` include rewrites by middleware added after the queue is wired, but not by middleware added at construction (for example by plugins, see [Chapter 19](Chapter_19.md#middleware)). `callback_handler` is left alone: a custom handler keeps working next to the queue, and only strands' default printing handler is replaced by a silent one so queue-wired agents do not print to stdout. `callback_handler: null` in `agent_kwargs` is untouched.

To attach a publisher to an agent you build yourself:

```python
publisher = EventPublisher(callback=on_event, agent_name="analyzer")
agent = Agent(hooks=[publisher])
agent.add_middleware(InvokeModelStage, publisher.observe_model_stream)
```

`make_event_queue` does this for every agent and for delegate-mode orchestrator agents. Swarm and Graph orchestrators get hooks only; their nodes are agents and stream their own tokens.

> **Tips & Tricks**
>
> - Call `wire_event_queue()` only **once** per `ResolvedConfig` — it mutates agents and orchestrators by adding hooks. Calling it twice would double-attach publishers.
> - Call `queue.flush()` between requests to clear stale events from a previous invocation. This also resets the `SESSION_START` / `SESSION_END` guards so the next cycle can re-emit them.
> - The queue has a max size of 10,000. If your agent generates more events than the consumer processes, events are dropped with a warning.
> - `SESSION_START` is emitted synchronously by `wire_event_queue()` before any agent runs. `SESSION_END` is emitted by `await queue.close()` — always call it in a `finally` block.

---

[Next: Chapter 16 — Name Sanitization →](Chapter_16.md)
