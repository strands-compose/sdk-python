# Chapter 14: Agent Factories — Custom Agent Construction

[← Back to Table of Contents](README.md) | [← Previous: Multi-File Configs](Chapter_13.md)

---

The `type` field on an agent lets you replace the standard `strands.Agent()` constructor with your own factory function. The `agent_kwargs` dict passes extra parameters to it.

```yaml
agents:
  assistant:
    type: ./factory.py:create_agent
    model: default
    system_prompt: "You are a helpful assistant."
    agent_kwargs:
      greeting: "Ahoy, captain!"
      personality: pirate
```

## Writing a Factory

strands-compose calls your factory with all standard agent parameters plus `agent_kwargs`:

```python
# factory.py
from strands import Agent

def create_agent(
    *,
    name: str,
    greeting: str = "Hello!",
    personality: str = "friendly",
    **kwargs,
) -> Agent:
    """Custom factory that injects personality into the system prompt."""
    system_prompt = kwargs.pop("system_prompt", "") or ""
    enhanced = f"{system_prompt}\nPersonality: {personality}. Greet with: {greeting}"

    return Agent(
        name=name,
        system_prompt=enhanced,
        **kwargs,
    )
```

**Important**: `strands.Agent.__init__` does NOT accept `**kwargs` — it has explicit parameters only. Your factory **must** consume any custom keys from `agent_kwargs` before forwarding the rest to `Agent()`.

## The `agent_kwargs` Dict

`agent_kwargs` accepts any key-value pairs that get spread into your factory call. It can also pass valid `Agent()` parameters directly:

```yaml
agents:
  assistant:
    model: default
    system_prompt: "You are helpful."
    agent_kwargs:
      record_direct_tool_call: true
      trace_attributes:
        team: content
        environment: production
```

When `type` is **not** set (standard agent construction), `agent_kwargs` is passed directly to `strands.Agent()`. Any invalid key will raise `TypeError` at construction time.

## Delegate `agent_kwargs` Override

Delegate orchestrations can also specify `agent_kwargs`, which get **merged** over the entry agent's kwargs (orchestration values win on conflict):

```yaml
agents:
  coordinator:
    model: default
    system_prompt: "Coordinate work."
    agent_kwargs:
      record_direct_tool_call: false

orchestrations:
  team:
    mode: delegate
    entry_name: coordinator
    agent_kwargs:
      record_direct_tool_call: true     # Overrides the agent's value
    connections:
      - agent: worker
        description: "Do the work."
```

> **Tips & Tricks**
>
> - Agent factories are great for custom `Agent` subclasses — your factory can return `MySpecialAgent(...)` which extends strands' `Agent`.
> - The factory must return a `strands.Agent` instance — strands-compose checks this and raises `TypeError` if it doesn't.
> - Use factory paths in the same format as hooks and tools: `./local/file.py:function_name` or `my_package.factory:create_agent`.

---

[Next: Chapter 15 — Event Streaming →](Chapter_15.md)
