# Chapter 16: Name Sanitization — How Names Are Handled

[← Back to Table of Contents](README.md) | [← Previous: Event Streaming](Chapter_15.md)

---

Names in config (agent names, model names, MCP client/server names, orchestration names) follow strict rules:

## Valid Names

- Characters: `[a-zA-Z0-9_-]`
- Length: 1–64 characters
- Examples: `researcher`, `fast-model`, `content_writer_v2`

## Automatic Sanitization

If you use characters outside the valid set (spaces, dots, special characters), strands-compose sanitizes them:

- Invalid characters → underscores
- Consecutive underscores → single underscore
- Leading/trailing underscores → stripped
- Names over 64 characters → truncated

```yaml
agents:
  "My Cool Agent!":      # Sanitized to: My_Cool_Agent
    system_prompt: "Hi."
```

A warning is logged when sanitization happens:

```
WARNING | section=<agents>, original=<My Cool Agent!>, sanitized=<My_Cool_Agent> | sanitized collection key
```

## Reference Updates

When a name is sanitized, **all references** to it throughout the config are updated automatically — `entry`, `model` references, `mcp` lists, orchestration agents, connections, and edges.

## Namespace Collisions

Agents and orchestrations share a single namespace. You cannot have:

```yaml
agents:
  team:
    system_prompt: "I'm an agent."

orchestrations:
  team:                    # ERROR: collides with agent 'team'
    mode: swarm
    agents: [team]
    entry_name: team
```

```
ValueError: Name collision between agents and orchestrations: ['team'].
Names must be unique within each section.
```

Models, MCP servers, and MCP clients each have their own independent namespaces — a model and an agent can share a name (though it's confusing and not recommended).

> **Tips & Tricks**
>
> - Stick to `snake_case` for names. It's valid, readable, and never needs sanitization.
> - Avoid naming an orchestration and an agent the same thing — even accidentally similar names can confuse you when debugging.

---

[Next: Chapter 17 — The Loading Pipeline →](Chapter_17.md)
