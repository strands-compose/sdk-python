# Chapter 4: YAML Anchors — DRY Config Blocks

[← Back to Table of Contents](README.md) | [← Previous: Variables](Chapter_03.md)

---

YAML has a built-in reuse mechanism: **anchors** (`&name`) and **aliases** (`*name`). strands-compose embraces this for eliminating copy-paste across your config.

## The `x-` Scratch Pad

Any top-level key starting with `x-` is treated as a scratch pad — it's stripped before schema validation. Use it to define reusable blocks:

```yaml
# Define reusable blocks
x-base_prompt: &base_prompt |
  You are a helpful assistant.
  Always be concise and clear.

x-safety_hooks: &safety_hooks
  - type: strands_compose.hooks:MaxToolCallsGuard
    params: { max_calls: 15 }
  - type: strands_compose.hooks:ToolNameSanitizer

x-model_params: &model_params
  max_tokens: 2048
  temperature: 0.7

# Use them
models:
  default:
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0
    params: *model_params        # Reuse the model params

agents:
  researcher:
    model: default
    system_prompt: *base_prompt   # Reuse the prompt
    hooks: *safety_hooks          # Reuse the hooks

  writer:
    model: default
    system_prompt: *base_prompt   # Same prompt, no copy-paste
    hooks: *safety_hooks          # Same hooks, no copy-paste

entry: researcher
```

## How Anchors Work

1. **Define** with `&name`: `x-my_block: &my_block { key: value }`
2. **Reference** with `*name`: `field: *my_block`

The anchor creates a deep copy at the alias site. The `x-` prefix is a strands-compose convention — YAML anchors work on any key, but `x-` keys are cleaned up so they don't trigger "unknown field" errors.

## Combining Anchors with Variables

Anchors and variables work together beautifully:

```yaml
vars:
  TONE: ${TONE:-professional}

x-base_prompt: &base_prompt |
  You are a ${TONE} assistant.
  Keep responses clear and structured.

agents:
  assistant:
    system_prompt: *base_prompt  # Gets "${TONE}" which is then interpolated
```

The order is: YAML parsing (anchors resolved) → anchor stripping (`x-*` removed) → variable interpolation (`${VAR}` replaced). So the alias `*base_prompt` is expanded first, and then `${TONE}` within it is interpolated.

## Anchors for Type-Preserving Reuse

Unlike variables (which can become strings when embedded), anchors always preserve the original YAML structure. An anchor on a dict gives you a dict, an anchor on a list gives you a list, an integer stays an integer:

```yaml
x-model_params: &params
  max_tokens: 2048    # integer
  temperature: 0.7    # float

models:
  fast:
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0
    params: *params   # max_tokens is still int 2048, not string "2048"
```

## Anchors You Can Define Anywhere

You don't *have* to use `x-` keys. Anchors can be defined on any value:

```yaml
models:
  default: &default_model        # Anchor on an entire model definition
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0

  backup: *default_model          # Exact copy of 'default'
```

The `x-` prefix is simply cleaner for "scratch pad" blocks that don't belong to any real config section.

> **Tips & Tricks**
>
> - Use `x-` blocks at the top of your file to define your project's "design system" — shared prompts, hook lists, model params.
> - Pair anchors with variables for maximum flexibility: anchors handle structure reuse, variables handle value swapping.
> - YAML anchors are resolved by the YAML parser itself — strands-compose doesn't even see them. This means they work exactly as documented in the YAML spec.
> - You can use `{ key: value }` inline syntax for short dicts in anchor definitions — great for concise params: `params: { max_calls: 15 }`.

---

[Next: Chapter 5 — Tools →](Chapter_05.md)
