# Chapter 12: Nested Orchestrations — Composing Systems

[← Back to Table of Contents](README.md) | [← Previous: Graph Conditions](Chapter_11.md)

---

Named orchestrations can reference each other. A swarm can be plugged into a delegate as a tool. A delegate can be a node in a graph. Compose them however you want.

```yaml
agents:
  researcher:
    model: default
    system_prompt: "Research topics thoroughly."

  reviewer:
    model: default
    system_prompt: "Review and improve content."

  qa_bot:
    model: default
    system_prompt: "Run quality checks on content."

  coordinator:
    model: default
    system_prompt: |
      1. Send work to content_team.
      2. Pass results to qa_bot.
      3. Return the final output.

orchestrations:
  # Inner orchestration — built first
  content_team:
    mode: swarm
    agents: [researcher, reviewer]
    entry_name: researcher
    max_handoffs: 10

  # Outer orchestration — references inner by name
  manager:
    mode: delegate
    entry_name: coordinator
    connections:
      - agent: content_team          # This is an orchestration, not a plain agent!
        description: "Content production team."
      - agent: qa_bot
        description: "Quality assurance check."

entry: manager
```

## How It Works

1. strands-compose collects all orchestration dependencies.
2. It performs a **topological sort** — inner orchestrations are built before outer ones.
3. Built orchestrations become nodes in the node pool, available for outer orchestrations to reference.
4. For delegate mode, inner orchestrations are wrapped as async tools (just like regular agents).

## Circular Dependencies

Orchestrations that reference each other in a cycle are caught at load time:

```yaml
orchestrations:
  a:
    mode: delegate
    entry_name: some_agent
    connections:
      - agent: b
        description: "..."
  b:
    mode: delegate
    entry_name: other_agent
    connections:
      - agent: a          # Circular!
        description: "..."
```

```
CircularDependencyError: Circular dependency between orchestrations: ['a', 'b'].
Orchestrations cannot reference each other in a cycle.
```

## Nesting Depth

There's no hard limit on nesting depth. A delegate can reference a graph that contains a delegate that references a swarm. As long as there are no cycles, it builds.

## Graph Nodes as Orchestrations

Graph edges can reference orchestrations, not just agents. This means a graph node can be an entire swarm:

```yaml
orchestrations:
  writing_team:
    mode: delegate
    entry_name: writer
    connections:
      - agent: researcher
        description: "Research first."

  pipeline:
    mode: graph
    entry_name: writing_team        # Starts with the delegate orchestration
    edges:
      - from: writing_team
        to: editor
      - from: editor
        to: publisher
```

> **Tips & Tricks**
>
> - Draw your system topology on paper first, then translate it to YAML. Each box is an agent or orchestration, each arrow is a connection/edge.
> - Name your orchestrations descriptively — `content_team`, `review_pipeline`, `analysis_graph` — because error messages reference these names.
> - Use delegate mode as the "outer shell" for most complex systems — it gives the coordinator explicit control over when to call sub-systems.

---

[Next: Chapter 13 — Multi-File Configs →](Chapter_13.md)
