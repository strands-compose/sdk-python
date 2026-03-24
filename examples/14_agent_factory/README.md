# 14 — Custom Agent Factory

> Replace the default `strands.Agent()` constructor with your own factory function — all from YAML.

## What this shows

- **`type:`** — point an agent at a custom callable instead of the built-in constructor
- **`agent_kwargs:`** — pass additional keyword arguments that only your factory understands
- Factory receives all standard params (`name`, `agent_id`, `model`, `system_prompt`, `tools`, `hooks`, `session_manager`) plus your extras

## How it works

```yaml
agents:
  assistant:
    type: ./factory.py:create_agent   # your factory, not Agent()
    model: default
    system_prompt: You are a helpful assistant.
    agent_kwargs:
      greeting: "Ahoy, captain!"
      personality: pirate
```

strands-compose imports `create_agent` from `factory.py` and calls it with
all the standard agent parameters **plus** everything in `agent_kwargs`.
Your factory must return a `strands.Agent` instance.

## Good to know

> **⚠️ `agent_kwargs` is an expert feature.**
>
> `strands.Agent.__init__()` does **not** accept `**kwargs` — it has a fixed set
> of explicit parameters.  strands-compose does **not** validate `agent_kwargs`
> at the schema level.  If invalid keys reach `Agent()`, you get a `TypeError`
> at runtime.
>
> **Your factory is responsible for:**
> 1. Consuming any custom keys (like `greeting`, `personality`) before forwarding.
> 2. Filtering the remaining kwargs to only Agent-accepted parameters.
>
> See `factory.py` in this example for the recommended pattern.

- You can also use `type:` with a module path: `my_package.factories:create_agent`.
- If a factory returns something other than `strands.Agent`, strands-compose raises a `TypeError` immediately.

## Prerequisites

```bash
pip install strands-compose
```

## Run

```bash
uv run python examples/14_agent_factory/main.py
```

## Try these prompts

| Prompt | What to expect |
|--------|----------------|
| `What is the meaning of life?` | Response starts with "Ahoy, captain!" in pirate style |
| `Tell me about Python.` | Pirate personality persists across messages |

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
