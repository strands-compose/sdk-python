# 02 — Variables & YAML Anchors

> Keep your config DRY — use variables for environment-specific values, anchors to reuse blocks.

## What this shows

- **Variables** (`${VAR:-default}`) — swap model IDs, feature flags, or tones per environment
  without editing the YAML.
- **YAML anchors** (`&name` / `*name`) — define a block once, reference it everywhere.
  Unlike variables (always strings), anchors preserve types: integers, booleans, objects.
- How both patterns combine for clean, environment-agnostic configs.

## How it works

The `vars:` block declares variables with fallback defaults. strands-compose resolves them
from environment variables first, then falls back to the inline default.

Anchors are plain YAML — you mark a block with `&anchor_name` and reference it with
`*anchor_name` anywhere in the same file. strands-compose doesn't do anything special here;
YAML handles the expansion.

```yaml
vars:
  MODEL: ${MODEL:-openai.gpt-oss-20b-1:0}    # env var -> falls back to default
  TONE:  ${TONE:-friendly}

x-base_prompt: &base_prompt |                 # define once
  You are a ${TONE} assistant.
  Keep answers clear and concise.

x-model_params: &model_params
  max_tokens: 512                              # stays an integer, not "512"

models:
  default:
    provider: bedrock
    model_id: ${MODEL}
    params: *model_params                      # reuse the block

agents:
  assistant:
    model: default
    system_prompt: *base_prompt                # reuse the prompt

entry: assistant
```

## Good to know

**Variables are always strings.** `${MAX_TOKENS:-512}` becomes `"512"`. If you need an
integer or boolean, use an anchor instead.

**Anchors are file-scoped.** An anchor defined in one YAML file can't be referenced from
another. For multi-file setups, see example 11.

**`x-` prefix is a convention**, not a requirement. Keys starting with `x-` are ignored by
strands-compose validation, so they're a safe place to park anchor definitions.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
# Linux / macOS
# Use built-in defaults
uv run python examples/02_vars_and_anchors/main.py

# Override tone or model at runtime
TONE=formal uv run python examples/02_vars_and_anchors/main.py
MODEL=us.anthropic.claude-sonnet-4-6-v1:0 uv run python examples/02_vars_and_anchors/main.py

# Windows PowerShell
# Use built-in defaults
uv run python examples/02_vars_and_anchors/main.py

# Override tone or model at runtime
$env:TONE="formal"; uv run python examples/02_vars_and_anchors/main.py
$env:MODEL="us.anthropic.claude-sonnet-4-6-v1:0"; uv run python examples/02_vars_and_anchors/main.py
```

## Try these prompts

- `What is the difference between a process and a thread?`
- `What year was Python first released?`
- `Explain what a Docker image is.`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
