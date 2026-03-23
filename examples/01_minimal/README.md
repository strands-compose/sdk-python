# 01 — Minimal Agent

> The absolute minimum: one model, one agent, one YAML file — start chatting.

## What this shows

- `load()` — the single entry point to strands-compose. Give it a YAML file, get back a
  ready-to-use agent.
- A minimal `config.yaml` with just a model and an agent — nothing else needed.
- `resolved.entry` — call it with a string and you get the agent's answer. No boilerplate.

## How it works

`load("config.yaml")` reads the file, creates a `BedrockModel` and a strands `Agent`, and
returns a `ResolvedConfig`. The `.entry` attribute is the agent you marked with `entry:` in
the YAML — you can call it directly like a function.

```yaml
# config.yaml — this is all you need
models:
  default:
    provider: bedrock
    model_id: openai.gpt-oss-20b-1:0

agents:
  assistant:
    model: default
    system_prompt: You are a concise and helpful assistant.

entry: assistant
```

```python
from strands_compose import load

resolved = load("config.yaml")
result = resolved.entry("What is Python?")
```

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/01_minimal/main.py
```

## Try these prompts

- `What is the capital of France?`
- `Explain what a Python generator is in one sentence.`
- `Write a haiku about software engineering.`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
