# 13 — Graph with Conditional Edges

> A graph that branches — edges fire only when a condition function returns True.

## What this shows

- `condition:` on graph edges — a Python callable that decides whether the edge fires
- How to build branching pipelines where one node routes to different next steps
- `reset_on_revisit:` — allows a node to run more than once (for retry loops)

## How it works

A regular graph edge always fires. A **conditional edge** fires only when its
`condition:` callable returns `True`. The callable receives the graph's
`GraphState` and returns a boolean:

```python
# conditions.py
from strands.multiagent.graph import GraphState


def needs_revision(state: GraphState) -> bool:
    """Route back to writer if the review says 'REVISE'."""
    return "REVISE" in str(state.results["reviewer"].result).upper()


def is_approved(state: GraphState) -> bool:
    """Route to publisher if the review says 'APPROVED'."""
    return "APPROVED" in str(state.results["reviewer"].result).upper()
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
`./file.py:func`). They receive the graph's `GraphState`, where
`state.results["<node>"].result` holds a finished node's result.

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

## Advanced topic — console output

Strands agents print their answer and tool calls through the default `callback_handler`.
This example's `main.py` prints nothing itself, so that output is all you see.
Set the handler to `null` in `agent_kwargs` to silence one agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```

Only silence helper agents in a multi-agent setup. On the agent that gives the final
answer, you would see no answer at all.
