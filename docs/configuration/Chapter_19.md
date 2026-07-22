# Chapter 19: Plugins — Reusable Agent Behaviors

[← Back to Table of Contents](README.md) | [← Previous: Full Reference](Chapter_18.md)

---

A plugin changes how an agent behaves. Rather than pack every instruction and safeguard
into one system prompt, you attach self-contained behaviour packages that plug into the
agent loop. The strands SDK ships several, and you can write your own. The ones you reach
for most often:

- **[Skills](https://strandsagents.com/docs/user-guide/concepts/plugins/skills/)** — on-demand instructions the agent discovers and loads only when relevant, so the base prompt stays lean.
- **[Steering](https://strandsagents.com/docs/user-guide/concepts/plugins/steering/)** — just-in-time guidance and guardrails for long, multi-step tasks.
- **[Context Offloader](https://strandsagents.com/docs/user-guide/concepts/plugins/context-offloader/)** — moves oversized tool results to storage and gives the agent a preview plus a retrieval tool.
- **[Context Injector](https://strandsagents.com/docs/user-guide/concepts/plugins/context-injector/)** — folds real-time facts (a clock, environment data, a lookup) into each model call without persisting them.
- **[GoalLoop](https://strandsagents.com/docs/user-guide/concepts/plugins/goal-loop/)** — validates a response and retries with feedback until it meets a quality bar.

The [strands plugins guide](https://strandsagents.com/docs/user-guide/concepts/plugins/)
covers the full set and how to build and distribute your own.

strands-compose does not reinvent any of this. It resolves each `plugins:` entry to one
live `strands.plugins.Plugin` and passes the list to `strands.Agent(plugins=[...])`. The
resolver validates that the result is a `Plugin` and otherwise gets out of the way.

---

## YAML Shape

A plugin entry is either an **inline object** or a **string shorthand**:

```yaml
agents:
  assistant:
    model: default
    plugins:
      # Inline object — type + optional params
      - type: strands:AgentSkills
        params:
          skills: ./skills

      # String shorthand — no params, just the import spec
      - ./plugins.py:MyPlugin
```

Both forms accept two import-spec styles:

- `module.path:Name` — resolved from an installed package (e.g. `strands:AgentSkills`, `strands.vended_plugins.goal:GoalLoop`).
- `./file.py:Name` — resolved from a local file, **relative to the config file**.

`params` is spread as keyword arguments to the resolved class or factory.

---

## Class vs. Factory

An entry may resolve to a **class** (a `Plugin` subclass) or a **factory** (any callable
that returns a `Plugin`). strands-compose calls the resolved object with `params` and
checks the result — a non-`Plugin` raises `TypeError`. The config looks the same either way.

Use a factory when a plugin needs a live argument that YAML can't express — a callable, a
storage backend, a set of providers. `ContextInjector`, for example, takes a render
callback:

```python
# plugins.py
from datetime import datetime, timezone

from strands.vended_plugins.context_injector import ContextInjector


def make_clock_injector() -> ContextInjector:
    """Build a ContextInjector that folds the current UTC time into each model call."""
    def render(_context: object) -> str:
        return f"<current_utc_time>{datetime.now(timezone.utc).isoformat()}</current_utc_time>"

    return ContextInjector(render, name="clock")
```

```yaml
agents:
  assistant:
    plugins:
      - type: ./plugins.py:make_clock_injector   # factory — no params needed
```

---

## Skills

`strands.AgentSkills` loads a directory of skills and exposes them through progressive
disclosure: each skill's name and description go into the system prompt at startup, and the
full instructions load only when the agent activates the skill. This keeps specialized,
occasionally-needed procedures out of the base prompt.

```yaml
agents:
  skilled_agent:
    model: default
    system_prompt: "You are a helpful assistant."
    plugins:
      - type: strands:AgentSkills
        params:
          skills: ./skills/     # one skill directory, or a parent of several
```

> **Note — path params are relative to the working directory.** A plugin's `type:` is
> resolved relative to the config file, but any path *inside* `params` (such as a skills
> directory) is forwarded verbatim and resolves against the current working directory. Run
> the config from a directory where that path is valid. (This may change in a future
> release.)

A skill is just a `SKILL.md` directory that `AgentSkills` discovers — authoring it (the
frontmatter fields, progressive disclosure, resource files) is owned by strands and the
open Agent Skills format, not by strands-compose. See
[strands — Skills](https://strandsagents.com/docs/user-guide/concepts/plugins/skills/) and
the [Agent Skills specification](https://agentskills.io/specification), and
`examples/15_plugins/` for a working one.

---

## Error Reference

| Condition | Exception |
|-----------|-----------|
| Malformed spec (no `:` separator) / missing file / module / attribute | `ImportResolutionError` (a `ValueError` subclass, from `load_object`) |
| Resolved object is not callable | `TypeError` |
| Resolved object is callable but does not return a `Plugin` | `TypeError` |
| Constructor or factory raises | the original exception, unwrapped |
| Two plugins on one agent share a `name` | `ValueError`, from the strands plugin registry |
| `plugins` also passed via `agent_kwargs` | `TypeError` (duplicate keyword), from `Agent()` |

strands-compose adds no plugin-specific exception types; everything propagates unwrapped.

---

> **Tips**
>
> - Every agent gets fresh plugin instances — two agents with the same entry never share state.
> - `plugins:` and `hooks:` can both appear on one agent and fire together.
> - A plugin's `@tool` methods are discoverable on the agent via `agent.tool_names` after construction.
> - Need only a lifecycle callback and no bundled tools or setup? A [hook](Chapter_06.md) is the lighter choice.

---

[← Previous: Full Reference](Chapter_18.md) | [Back to Table of Contents](README.md)
