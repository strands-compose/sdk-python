# Chapter 10: Orchestrations — Multi-Agent Systems

[← Back to Table of Contents](README.md) | [← Previous: MCP](Chapter_09.md)

---

Orchestrations wire multiple agents into collaborative systems. Define them under the `orchestrations` section — each one has a `mode` and references agents by name.

**Key rule**: agents and orchestrations share a single namespace. You can't have an agent named `team` and an orchestration named `team`.

## Mode: Delegate

A coordinator agent calls sub-agents as tool functions. Best for hub-and-spoke patterns where one agent directs others:

```yaml
agents:
  researcher:
    model: default
    system_prompt: "You research topics thoroughly."

  writer:
    model: default
    system_prompt: "You write polished articles."

  coordinator:
    model: default
    system_prompt: |
      For every request:
        1. Call researcher to gather facts.
        2. Pass the facts to writer for the final article.
      Delegate all work — don't write content yourself.

orchestrations:
  team:
    mode: delegate
    entry_name: coordinator
    connections:
      - agent: researcher
        description: "Research a topic and return structured facts."
      - agent: writer
        description: "Write a polished article from research material."

entry: team
```

**How it works**: strands-compose **forks** a new agent from the `entry_name` agent's blueprint (model, system_prompt, hooks, tools) and adds delegate tools for each connection. The original `coordinator` agent is **never mutated**. Each connection becomes an async tool that the coordinator can call.

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | `"delegate"` | Yes | |
| `entry_name` | string | Yes | The agent whose blueprint is forked as coordinator |
| `connections` | list | Yes | Sub-agents to wire as tools |
| `connections[].agent` | string | Yes | Name of the target agent or orchestration |
| `connections[].description` | string | Yes | Tool description the LLM sees |
| `session_manager` | dict | No | Override session manager for the forked agent |
| `hooks` | list | No | Additional hooks for the forked agent |
| `agent_kwargs` | dict | No | Override agent kwargs (merged with entry agent's kwargs) |

## Mode: Swarm

Peer agents hand off control to each other autonomously. No central coordinator — agents decide when to pass the baton:

```yaml
agents:
  drafter:
    model: default
    system_prompt: |
      Write initial code. When done, hand off to reviewer.

  reviewer:
    model: default
    system_prompt: |
      Review code. If issues found, hand back to drafter.
      If good, hand off to tech_lead.

  tech_lead:
    model: default
    system_prompt: "Make final approval decision."

orchestrations:
  review_team:
    mode: swarm
    agents: [drafter, reviewer, tech_lead]
    entry_name: drafter
    max_handoffs: 10

entry: review_team
```

**How it works**: strands' Swarm injects a `handoff_to_agent` tool into every agent in the list. Agents call this tool to transfer control. Execution continues until one agent decides to stop or `max_handoffs` is reached.

**Fields**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `mode` | `"swarm"` | Yes | | |
| `agents` | list[str] | Yes | | Agent names participating in the swarm |
| `entry_name` | string | Yes | | Which agent starts first |
| `max_handoffs` | int | No | 20 | Maximum handoffs before termination |
| `max_iterations` | int | No | 20 | Maximum iterations |
| `execution_timeout` | float | No | 900.0 | Total execution timeout (seconds) |
| `node_timeout` | float | No | 300.0 | Per-agent timeout (seconds) |
| `session_manager` | dict | No | | Swarm-level session manager |
| `hooks` | list | No | | Swarm-level hooks |

**Limitation**: All swarm nodes must be plain agents — no nested orchestrations. Node agents cannot have session managers (see [Chapter 7](Chapter_07.md#swarm-agents-and-sessions)).

## Mode: Graph

Deterministic DAG pipeline with explicit edges. Agents execute in dependency order — independent nodes can run in parallel:

```yaml
agents:
  planner:
    model: default
    system_prompt: "Create a content outline."

  writer:
    model: default
    system_prompt: "Write content following the outline."

  editor:
    model: default
    system_prompt: "Edit for clarity and correctness."

orchestrations:
  pipeline:
    mode: graph
    entry_name: planner
    edges:
      - from: planner
        to: writer
      - from: writer
        to: editor

entry: pipeline
```

**How it works**: strands-compose feeds the edges to strands' `GraphBuilder`, which constructs a topological execution plan. The `entry_name` must be a node with no incoming edges (the pipeline start).

**Fields**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `mode` | `"graph"` | Yes | | |
| `entry_name` | string | Yes | | Starting node (must have no incoming edges) |
| `edges` | list | Yes | | Edge definitions |
| `edges[].from` | string | Yes | | Source node name |
| `edges[].to` | string | Yes | | Target node name |
| `edges[].condition` | string | No | | Python callable for conditional routing |
| `max_node_executions` | int | No | | Max times any node can execute |
| `execution_timeout` | float | No | | Total pipeline timeout (seconds) |
| `node_timeout` | float | No | | Per-node timeout (seconds) |
| `reset_on_revisit` | bool | No | false | Reset agent state when a node is revisited |
| `session_manager` | dict | No | | Graph-level session manager |
| `hooks` | list | No | | Graph-level hooks |

> **Tips & Tricks**
>
> - **Delegate** is best for "boss and workers" patterns — the coordinator has full control over when and how to call sub-agents.
> - **Swarm** is best for peer collaboration — agents negotiate among themselves. Great for review/revision cycles.
> - **Graph** is best for fixed pipelines — when you know the exact processing order. Parallel execution of independent nodes is automatic.
> - The `description` field on delegate connections is what the coordinator LLM sees as the tool description — make it clear and actionable.
> - In swarm mode, guide handoff behavior through system prompts — tell each agent *when* and *to whom* they should hand off.

---

[Next: Chapter 11 — Graph Conditions →](Chapter_11.md)
