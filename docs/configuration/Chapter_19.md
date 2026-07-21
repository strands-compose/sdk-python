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

> **Paths in `params` are not rewritten.** Unlike a plugin's `type:` (which is resolved
> relative to the config file), everything under `params` is forwarded to the plugin
> verbatim. `skills: ./skills/` therefore resolves against the process working directory —
> run the config from the directory that makes that path valid.

### Authoring a skill (SKILL.md)

Agent Skills is an open, cross-vendor format — originated by Anthropic and adopted across
agent tooling. A skill is a directory (named after the skill) containing a `SKILL.md`: YAML
frontmatter followed by a markdown body. It may also ship resource directories the agent
reads on demand.

```
conventional-commits/
├── SKILL.md          # required — frontmatter + instructions
├── scripts/          # optional — runnable scripts
├── references/       # optional — docs loaded only when needed
└── assets/           # optional — templates, data, images
```

Frontmatter fields, per the [Agent Skills specification](https://agentskills.io/specification):

| Field | Required | Notes |
|-------|----------|-------|
| `name` | yes | 1–64 chars; lowercase `a–z`, `0–9`, `-`; no leading/trailing or consecutive hyphens. **Must match the directory name.** |
| `description` | yes | 1–1024 chars. State *what* it does **and** *when* to use it, with keywords the model can match — this is all the agent sees until it activates the skill. |
| `license` | no | A license name or a bundled license file. |
| `compatibility` | no | ≤500 chars. Environment requirements (target product, system packages, network access). |
| `metadata` | no | Arbitrary string-to-string map for client-specific data. |
| `allowed-tools` | no | Space-separated pre-approved tool names (experimental; support varies). |

```markdown
---
name: conventional-commits
description: Write git commit messages that follow the Conventional Commits standard. Use when the user asks for a commit message or wants a change summary written up for git.
license: Apache-2.0
---

# Conventional Commits

## When to use
Activate when the user asks for a commit message...

## Steps
1. Choose the single type that best fits the change...

## Examples
Input: "added pagination to the users endpoint" -> `feat(api): add pagination to the users endpoint`

## Edge cases
- Several unrelated changes -> recommend separate commits.
```

**Write for progressive disclosure.** The `description` is the model's only cue to activate
the skill, so make it specific. Keep the body focused — the spec recommends under ~500 lines
(≈5000 tokens) — and move long reference material into `references/` files that load only
when the task needs them.

> **Resource files need a tool.** `AgentSkills` handles discovery and activation only. A
> skill that ships scripts or references also needs a file-reading tool such as `file_read`
> from [`strands-agents-tools`](https://strandsagents.com/docs/user-guide/concepts/plugins/skills/#providing-tools-for-resource-access);
> add it under the agent's `tools:`. Instruction-only skills need none.

### Further reading

- [strands — Skills](https://strandsagents.com/docs/user-guide/concepts/plugins/skills/) — how `AgentSkills` discovers, activates, and persists skills (start here).
- [Agent Skills specification](https://agentskills.io/specification) and the [agentskills/agentskills](https://github.com/agentskills/agentskills) repo — the open format itself, plus the `skills-ref` validator.
- [Anthropic — Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) — the rationale behind the format.

---

## Error Reference

| Condition | Exception |
|-----------|-----------|
| `type` has no `:` separator | `ValueError` |
| Malformed spec / missing file / module / attribute | `ImportResolutionError` (a `ValueError` subclass, from `load_object`) |
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
