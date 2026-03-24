# 10 — Nested Orchestration

> A swarm inside a delegate — compose orchestrations like building blocks.

## What this shows

- **Referencing an orchestration inside another orchestration** — `content_team` (swarm)
  is used as a child node in `manager` (delegate)
- **Topological sort** — strands-compose builds `content_team` before `manager` automatically
- How agents, swarms, and graphs all become first-class nodes in a larger system

## How it works

```
manager (delegate)
  ├── content_team (swarm)  — researcher ↔ reviewer
  └── qa_bot        (agent) — quality-checks the final output
```

The coordinator never writes content itself — it delegates content production to the
swarm and quality assurance to `qa_bot`. From the coordinator's perspective,
`content_team` is just another tool.

```yaml
orchestrations:
  content_team:
    mode: swarm
    agents: [researcher, reviewer]
    entry_name: researcher
    max_handoffs: 10

  manager:
    mode: delegate
    entry_name: coordinator
    connections:
      - agent: content_team     # ← references the swarm above
        description: "Content production team: researches and prepares the content."
      - agent: qa_bot
        description: "Quality assurance: checks the final content for accuracy and completeness."
```

strands-compose topologically sorts the orchestrations: `content_team` is built first,
then `manager` wraps it as a delegate tool.

## Good to know

**Agents and orchestrations share a single namespace.** You can't have an agent and an
orchestration with the same name — strands-compose raises an error.

**Why YAML wins here.** The programmatic version would need ~60 lines to recreate what
YAML expresses in 20. More importantly, the orchestration *structure* is immediately
readable — you see the full system topology at a glance.

**You can nest arbitrarily.** A graph can include a delegate which includes a swarm.
As long as there are no cycles in the orchestration dependency graph, strands-compose
sorts and builds everything.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/10_nested/main.py
```

## Try these prompts

- `Create a comprehensive guide to setting up CI/CD with GitHub Actions.`
- `Produce a well-researched article about the future of edge computing.`
- `Write a technical deep-dive on how database indexes work.`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
