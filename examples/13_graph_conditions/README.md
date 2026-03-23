# 13 — Graph with Conditional Edges

> A graph that branches — edges fire only when a condition function returns True.

## What this shows

- `condition:` on graph edges — a Python callable that decides whether the edge fires
- How to build branching pipelines where one node routes to different next steps
- `reset_on_revisit:` — allows a node to run more than once (for retry loops)

## How it works

A regular graph edge always fires. A **conditional edge** fires only when its
`condition:` callable returns `True`. The callable receives a context dict and
returns a boolean:

```python
# conditions.py
def needs_revision(context: dict) -> bool:
    """Route back to writer if the review says 'REVISE'."""
    last_output = str(context.get("last_output", ""))
    return "REVISE" in last_output.upper()

def is_approved(context: dict) -> bool:
    """Route to publisher if the review says 'APPROVED'."""
    last_output = str(context.get("last_output", ""))
    return "APPROVED" in last_output.upper()
```

Wire them in YAML:

```yaml
orchestrations:
  pipeline:
    mode: graph
    entry_name: writer
    reset_on_revisit: true
    edges:
      - from: writer
        to: reviewer
      - from: reviewer
        to: writer                          # retry loop
        condition: ./conditions.py:needs_revision
      - from: reviewer
        to: publisher                       # happy path
        condition: ./conditions.py:is_approved
```

This creates a loop: writer -> reviewer -> (back to writer if revisions needed, forward
to publisher if approved).

## Good to know

**`reset_on_revisit: true`** is required for loops. Without it, a node that already ran
won't execute again — the edge is silently skipped.

**Conditions are Python callables**, loaded via import path (`module:func` or
`./file.py:func`). They receive a dict with the graph's execution context.

**If no conditional edge fires**, the graph stops at that node. Make sure your
conditions are exhaustive — or add a fallback unconditional edge.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/13_graph_conditions/main.py
```

## Try these prompts

- `Write a short Python tutorial about list comprehensions.`
- `Write a paragraph explaining what Docker containers are.`
- `Create a quick guide to Python's asyncio library.`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
