# Chapter 2: Models — Choosing Your LLM

[← Back to Table of Contents](README.md) | [← Previous: The Basics](Chapter_01.md)

---

The `models` section defines named LLM configurations. Each model has a `provider`, a `model_id`, and optional `params`.

```yaml
models:
  fast:
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0

  creative:
    provider: openai
    model_id: gpt-4o
    params:
      temperature: 0.9

  local:
    provider: ollama
    model_id: llama3.2
    params:
      ctx_size: 8192
```

## Built-in Providers

| Provider | Package Required | Example `model_id` |
|----------|-----------------|---------------------|
| `bedrock` | *(included)* | `us.anthropic.claude-sonnet-4-6-v1:0` |
| `openai` | `pip install strands-compose[openai]` | `gpt-4o` |
| `ollama` | `pip install strands-compose[ollama]` | `llama3.2` |
| `gemini` | `pip install strands-compose[gemini]` | `gemini-2.0-flash` |

## How Agents Reference Models

Agents reference models by **name** — the key you defined in the `models` section:

```yaml
models:
  smart:
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0

agents:
  analyst:
    model: smart     # <-- references the "smart" model above
    system_prompt: "You analyze data."
```

## Inline Models

Don't want to name a model? Define it inline directly on the agent:

```yaml
agents:
  analyst:
    model:
      provider: bedrock
      model_id: us.anthropic.claude-sonnet-4-6-v1:0
    system_prompt: "You analyze data."
```

This is handy when only one agent uses a specific model — no need to pollute the `models` section. But if two agents share the same model config, **use a named model** to avoid duplication.

## Custom Model Providers

If the built-in four providers aren't enough, you can point `provider` to a custom `Model` subclass:

```yaml
models:
  my_custom:
    provider: my_package.models:CustomModel
    model_id: my-model-v1
    params:
      api_key: ${API_KEY}
```

The class must be a subclass of `strands.models.Model`. The `model_id` and `params` are passed to its constructor.

## The `params` Dict

`params` is a pass-through dictionary — whatever you put in it gets forwarded as `**kwargs` to the model constructor. This means you can set any provider-specific parameter:

```yaml
models:
  tuned:
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0
    params:
      max_tokens: 4096
      temperature: 0.7
      top_p: 0.9
```

> **Tips & Tricks**
>
> - When combined with `vars`, you can swap models at runtime: `MODEL=gpt-4o python main.py`. See [Chapter 3](Chapter_03.md).
> - If you omit `model` on an agent entirely, strands picks its built-in default (Bedrock). This is fine for quick tests but explicit is better for production.
> - The `params` dict preserves types from YAML — integers stay integers, floats stay floats. This matters for parameters like `max_tokens` that must be an int.

---

[Next: Chapter 3 — Variables →](Chapter_03.md)
