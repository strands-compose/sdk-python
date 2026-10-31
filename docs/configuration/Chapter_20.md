# Chapter 20: Structured Output — Typed Agent Results

[← Back to Table of Contents](README.md) | [← Previous: Plugins](Chapter_19.md)

---

By default an agent answers with text. With `structured_output`, it fills a pydantic model
you define, and every call returns an instance of that model. Your code reads typed fields
instead of parsing text.

strands-compose loads the class and passes it to `strands.Agent(structured_output_model=...)`.
strands does the rest.

```yaml
agents:
  triage:
    model: default
    system_prompt: "You triage customer support messages."
    structured_output:
      model: ./schemas.py:Ticket                               # required
      prompt: "Fill the Ticket schema for the message above."  # optional
```

```python
# schemas.py
from typing import Literal

from pydantic import BaseModel, Field


class Ticket(BaseModel):
    category: Literal["billing", "bug", "feature_request", "other"]
    priority: Literal["low", "medium", "high"]
    summary: str = Field(description="One sentence that states the problem.")
```

```python
from strands_compose import load

agent = load("config.yaml").agents["triage"]
ticket = agent("I was charged twice this month!").structured_output
print(ticket.category, ticket.priority)  # billing high
```

---

## Fields

| Field | Required | What it does |
|-------|----------|--------------|
| `model` | yes | Import spec of a pydantic `BaseModel` subclass: `module.path:Name` or `./file.py:Name`, **relative to the config file**. |
| `prompt` | no | Message strands sends when the model answers without filling the schema. Default: `"You must format the previous response as structured output."` |

---

## What a Call Returns

- `result.structured_output` is the model instance.
- `str(result)` is the instance as JSON.
- When a field fails validation (for example a value outside a `Literal`), strands sends the
  errors back to the model so it can fix them.
- When the model still does not fill the schema, the call raises strands'
  `StructuredOutputException` (from `strands.types.exceptions`).
- One call can ask for a different class: `agent(prompt, structured_output_model=Other)`
  overrides the YAML default for that call only.

---

## In Orchestrations

- **Graph**: an edge condition can branch on a field instead of matching keywords. See
  [Chapter 11](Chapter_11.md#routing-on-structured-output).
- **Delegate**: when a coordinator calls a structured-output agent through a connection,
  the tool result it gets back is the object as JSON.

---

## Agent Factories and `agent_kwargs`

- A custom factory (`type:`, [Chapter 14](Chapter_14.md)) receives `structured_output_model`
  and `structured_output_prompt` only when `structured_output` is set. A factory with a fixed
  signature keeps working without them.
- `structured_output_model` and `structured_output_prompt` inside `agent_kwargs` are rejected
  when the config is parsed. Use `structured_output` instead.

---

## Error Reference

| Condition | Exception |
|-----------|-----------|
| `structured_output` without `model` | `SchemaValidationError`, when the config is parsed |
| `structured_output_model` or `structured_output_prompt` in `agent_kwargs` | `SchemaValidationError`, when the config is parsed |
| The spec cannot be imported | `ImportResolutionError`, from `load()` |
| The spec is not a pydantic `BaseModel` subclass | `TypeError`, from `load()` |
| The model never fills the schema | `StructuredOutputException`, from strands, when the agent is called |

---

> **Tips**
>
> - The model sees the schema. `Field(description=...)` on each field tells it what to put there.
> - Use `Literal[...]` for fixed choices; your code can then branch on the value safely.
> - `examples/16_structured_output/` is a runnable triage agent built this way.

---

[← Previous: Plugins](Chapter_19.md) | [Back to Table of Contents](README.md)

**Bonus**: [Quick Recipes →](Quick_Recipes.md)
