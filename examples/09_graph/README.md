# 09 — Graph Pipeline

> A fixed pipeline — nodes execute in the order you define, no surprises.

## What this shows

- `mode: graph` in `orchestrations:` — a deterministic DAG with explicit edges
- `edges:` list — each edge is a `from: -> to:` pair that locks in execution order
- `entry_name:` — the starting node (must have no incoming edges)
- The difference between graph and swarm: you decide the order, not the agents

## How it works

A graph pipeline executes nodes in topological order. The output of each node is
passed as context to the next.

```
content_strategist ──▶ content_writer ──▶ copy_editor
```

In YAML, edges are explicit `from: / to:` pairs:

```yaml
orchestrations:
  blog_pipeline:
    mode: graph
    entry_name: content_strategist
    edges:
      - from: content_strategist
        to: content_writer
      - from: content_writer
        to: copy_editor
```

That's it — three agents, two edges, one pipeline. strands-compose builds the DAG
and runs each node in sequence.

## Good to know

**Graph vs Swarm vs Delegate.** Use graph when the execution order is fixed and
known upfront — e.g. content pipelines, multi-stage validation, ETL. Use swarm for
collaborative back-and-forth. Use delegate for a coordinator that picks tools on the fly.

**Nodes at the same depth can run in parallel.** If two nodes share no dependency,
strands executes them concurrently — but that's handled for you.

**Conditional edges** are supported too — see example 13 for that.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/09_graph/main.py
```

## Try these prompts

- `Write a blog post about why Rust is gaining popularity among Python developers.`
- `Create a post about the importance of code review in software teams.`
- `Write about how large language models are changing software development.`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
