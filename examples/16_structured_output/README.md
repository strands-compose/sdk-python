# 16 — Structured Output

> The agent returns a typed Python object instead of free text.

## What this shows

- `structured_output:` — point an agent at a pydantic model; every call returns an instance of it
- `result.structured_output` — read typed fields in your code, no text parsing
- `prompt:` — the follow-up message strands sends when the model answers without filling the schema

## How it works

Define the shape you want as a pydantic model:

```python
# schemas.py
class Ticket(BaseModel):
    category: Literal["billing", "bug", "feature_request", "other"]
    priority: Literal["low", "medium", "high"]
    summary: str
    needs_human: bool
```

Point the agent at it:

```yaml
agents:
  triage:
    model: default
    system_prompt: You triage customer support messages.
    structured_output:
      model: ./schemas.py:Ticket                          # relative to this config
      prompt: Fill the Ticket schema for the message above.  # optional
```

Every call now returns a `Ticket`:

```python
result = agent("The export button crashes the app.")
ticket = result.structured_output  # Ticket(category='bug', priority='high', ...)
if ticket.needs_human:
    ...
```

## Good to know

**The model sees the schema.** `Field(description=...)` on each field tells it what to
put there; `schemas.py` uses this for every field.

**Wrong values go back to the model.** If a field fails validation, such as a priority
outside the `Literal`, strands sends the errors back so the model can fix them. If it
still cannot fill the schema, the call raises `StructuredOutputException`.

**`str(result)` is JSON.** Handy for logging or for passing the result on.

**Routing in a graph.** An edge condition can read a field instead of matching keywords —
see [Chapter 11](../../docs/configuration/Chapter_11.md#routing-on-structured-output).
The full reference is [Chapter 20](../../docs/configuration/Chapter_20.md).

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/16_structured_output/main.py
```

## Try these prompts

- `I was charged twice for my subscription this month and nobody has replied.`
- `The export button crashes the app every time I click it.`
- `It would be great if I could change the dashboard colors.`
