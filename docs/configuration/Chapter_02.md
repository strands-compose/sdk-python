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
    model_id: gpt-5.5
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
| `openai` | `pip install strands-compose[openai]` | `gpt-5.5` |
| `ollama` | `pip install strands-compose[ollama]` | `llama3.2` |
| `gemini` | `pip install strands-compose[gemini]` | `gemini-3.6-flash` |
| `anthropic` | `pip install strands-compose[anthropic]` | `claude-sonnet-4-6` |

> **Anthropic note:** the `anthropic` provider talks to the Anthropic API directly
> (not through Bedrock) and **requires `max_tokens` in `params`** — the API mandates
> it, unlike the other providers:
>
> ```yaml
> models:
>   claude:
>     provider: anthropic
>     model_id: claude-sonnet-4-6
>     params:
>       max_tokens: 4096          # required by the Anthropic API
> ```
>
> Set the API key via the `ANTHROPIC_API_KEY` environment variable, or pass
> `params.client_args.api_key`.

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

If the built-in five providers aren't enough, you can point `provider` to a custom `Model` subclass:

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

## Prompt Caching

Set `cache` on a model, next to `provider` and `model_id`. It becomes strands' `CacheConfig` and is passed to the model as `cache_config`:

```yaml
models:
  fast:
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0
    cache: true                          # automatic caching
  long_context:
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0
    cache: {strategy: auto, ttl: 1h}     # any CacheConfig field
```

| `cache` | Result |
|---------|--------|
| absent or `false` | caching off (the default) |
| `true` | `CacheConfig(strategy="auto")` |
| mapping | `CacheConfig(**mapping)` |

The mapping keys are `strategy` (`auto` or `anthropic`), `ttl`, `system_prompt_ttl`, `tools_ttl` and `cache_key`; an unknown key fails at load time. Caching is configured only through `cache`: `params.cache_config` is rejected.

Each provider applies the fields it supports:

| Provider | Effect |
|----------|--------|
| `bedrock` | Adds cache points for models that support them (Claude). Other models are skipped with a log line; GPT models on Bedrock cache automatically without it. |
| `anthropic` | Adds cache points. |
| `openai` | Uses `cache_key` to route requests to the provider's automatic cache. |
| `ollama` | Ignored. |
| `gemini` | Not passed: strands' Gemini model has no `cache_config`. |
| custom | Receives `cache_config` as a constructor argument. |

On Claude the first call writes the cache (billed above the normal input price) and later calls with the same prefix read it (billed far below it), so caching pays off for agents that reuse a long system prompt or tool list. Cache reads and writes show up in `AGENT_COMPLETE` as `cache_read_input_tokens` and `cache_write_input_tokens` ([Chapter 15](Chapter_15.md)).

> **Tips & Tricks**
>
> - When combined with `vars`, you can swap models at runtime: `MODEL=gpt-5.5 python main.py`. See [Chapter 3](Chapter_03.md).
> - If you omit `model` on an agent entirely, strands picks its built-in default (Bedrock). This is fine for quick tests but explicit is better for production.
> - The `params` dict preserves types from YAML — integers stay integers, floats stay floats. This matters for parameters like `max_tokens` that must be an int.

---

[Next: Chapter 3 — Variables →](Chapter_03.md)
