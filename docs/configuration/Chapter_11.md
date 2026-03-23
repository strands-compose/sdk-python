# Chapter 11: Graph Conditions — Dynamic Routing

[← Back to Table of Contents](README.md) | [← Previous: Orchestrations](Chapter_10.md)

---

Graph edges can have conditions — Python functions that decide at runtime whether an edge should fire. This unlocks feedback loops and branching pipelines.

```yaml
orchestrations:
  pipeline:
    mode: graph
    entry_name: writer
    reset_on_revisit: true
    max_node_executions: 6
    edges:
      - from: writer
        to: reviewer
      - from: reviewer
        to: writer
        condition: ./conditions.py:needs_revision
      - from: reviewer
        to: publisher
        condition: ./conditions.py:is_approved
```

## Writing Condition Functions

Condition functions receive the graph execution context and return `True` or `False`:

```python
# conditions.py

def needs_revision(context: dict) -> bool:
    """Route back to writer if reviewer says REVISE."""
    last_output = str(context.get("last_output", ""))
    return "REVISE" in last_output.upper()

def is_approved(context: dict) -> bool:
    """Route to publisher if reviewer approves."""
    last_output = str(context.get("last_output", ""))
    return "APPROVED" in last_output.upper()
```

The condition spec format is the same as tools and hooks: `./file.py:function_name` or `module.path:function_name`.

## Loops and Revisits

When an edge condition creates a loop (reviewer → writer → reviewer), you need two settings:

- **`reset_on_revisit: true`** — Resets the agent's conversation state when it's visited again. Without this, the agent accumulates context from all previous visits.
- **`max_node_executions: N`** — Safety cap on how many times any node can execute. Prevents infinite loops.

## How Conditions Are Evaluated

For a given node, all outgoing edges are checked. Edges without conditions always fire. Edges with conditions fire only if the function returns `True`. If no outgoing edge fires, the pipeline stops.

> **Tips & Tricks**
>
> - Make your reviewer agent's output deterministic by instructing it to start with keywords like "REVISE:" or "APPROVED:" — this makes condition functions simple and reliable.
> - Always set `max_node_executions` when you have loops — it's your safety net against infinite cycles.
> - `reset_on_revisit` is usually what you want for revision loops — the writer should get fresh context each time, not accumulate all previous attempts.
> - Condition functions must be callable. If you accidentally point to a non-callable (like a string or class), strands-compose will raise a clear error.

---

[Next: Chapter 12 — Nested Orchestrations →](Chapter_12.md)
