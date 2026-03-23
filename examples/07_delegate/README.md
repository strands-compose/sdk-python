# 07 — Delegate (Multi-Agent Coordination)

> One agent calls others as tools — research, write, done.

## What this shows

- `mode: delegate` in `orchestrations:` — turns sub-agents into callable tools
- `entry_name:` — explicitly names the coordinator agent whose blueprint is used
- `connections:` — a flat list of child agents, each with a `description:` the
  coordinator sees when deciding which tool to call
- The simplest multi-agent pattern: a coordinator that delegates, never writes itself

## How it works

Define your agents normally, then wire them with an orchestration:

```yaml
orchestrations:
  main:
    mode: delegate
    entry_name: coordinator
    connections:
      - agent: researcher
        description: "Research a topic and return structured facts."
      - agent: writer
        description: "Write a report from the provided facts."
```

`entry:` points at the orchestration name (`main`), which is all you need in `main.py`.

When `load()` resolves the orchestration, it **forks a brand-new Agent** from the
`coordinator` blueprint (model, system prompt, hooks, kwargs — everything). `researcher`
and `writer` are each wrapped as async `@tool` functions and added to that new agent.
The original `coordinator` agent defined under `agents:` is never mutated.

```
coordinator blueprint
  └── forked into new Agent
        ├── researcher (tool)  — gathers facts
        └── writer     (tool)  — turns facts into a report
```

The forked agent's `agent_id` is the orchestration name (`main`), making it easy to
trace in logs. Any `agent_kwargs` defined on the orchestration are merged on top of
the coordinator's own kwargs — orchestration values win on conflict.

## Good to know

**The fork, not the original.** The agent you interact with via `resolved.entry` is the
newly built fork, not the `coordinator` you declared. This matters if you pass the same
agent into multiple orchestrations — each one gets its own independent copy.

**Each sub-agent is independent.** It gets its own model, system prompt, tools, and hooks.
The coordinator (fork) only sees the `description:` string — it can't peek inside.

**The coordinator should not write content itself.** Its job is to call the right sub-agent
at the right time and pass through the result. The system prompt enforces this.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/07_delegate/main.py
```

## Try these prompts

- `Write a short guide on how Python manages memory.`
- `Create a report on the benefits of test-driven development.`
- `Produce a concise overview of how HTTP/2 improves on HTTP/1.1.`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
