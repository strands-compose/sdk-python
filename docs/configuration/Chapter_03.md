# Chapter 3: Variables — Environment-Driven Config

[← Back to Table of Contents](README.md) | [← Previous: Models](Chapter_02.md)

---

strands-compose supports Docker Compose-style `${VAR}` interpolation. Define variables in the `vars` block, reference them anywhere with `${VAR}`, and optionally provide defaults with `${VAR:-fallback}`.

```yaml
vars:
  MODEL: ${MODEL:-us.anthropic.claude-sonnet-4-6-v1:0}
  TONE:  ${TONE:-friendly}
  MAX_TOKENS: ${MAX_TOKENS:-1024}

models:
  default:
    provider: bedrock
    model_id: ${MODEL}
    params:
      max_tokens: ${MAX_TOKENS}

agents:
  assistant:
    model: default
    system_prompt: "You are a ${TONE} assistant."

entry: assistant
```

## Lookup Order

When strands-compose sees `${SOMETHING}`, it resolves it in this order:

1. **`vars` block** — your YAML-defined variables
2. **Environment variables** — `os.environ`
3. **Default value** — the part after `:-`
4. **Error** — if none of the above, loading fails with a clear message

So `${MODEL:-gpt-4o}` means: "use the `MODEL` var if defined, then check the environment, then fall back to `gpt-4o`."

## Override at Runtime

```bash
# Linux/macOS
TONE=formal MODEL=gpt-4o python main.py

# Windows PowerShell
$env:TONE="formal"; $env:MODEL="gpt-4o"; python main.py
```

## Variable Chaining

Variables can reference other variables:

```yaml
vars:
  BASE_MODEL: us.anthropic.claude-sonnet-4-6-v1:0
  MODEL: ${BASE_MODEL}
```

This works because strands-compose resolves `vars` in two sequential passes — the first pass resolves against environment variables, the second pass resolves cross-references between vars. Circular references (`A: ${B}`, `B: ${A}`) are caught and raise a clear error.

## Type Preservation

Here's a subtle but powerful feature: when the **entire** value is a single `${VAR}` reference (not embedded in a larger string), the original type is preserved.

```yaml
vars:
  MAX_TOKENS: 1024    # This is an integer in YAML

models:
  default:
    provider: bedrock
    model_id: some-model
    params:
      max_tokens: ${MAX_TOKENS}   # Resolves to integer 1024, not string "1024"
```

But if you embed it in a string, it becomes a string:

```yaml
system_prompt: "Use max ${MAX_TOKENS} tokens"  # "Use max 1024 tokens" (string)
```

This is important for parameters that expect a specific type (like `max_tokens` needing an int).

## Variables Without Defaults

If you reference a variable that doesn't exist and has no default, loading fails immediately:

```yaml
vars:
  MODEL: ${REQUIRED_MODEL}  # No :- default!
```

```
ValueError: Variable '${REQUIRED_MODEL}' is not set in 'vars:' or environment,
and no default was provided.
Use ${REQUIRED_MODEL:-fallback} to set a fallback value.
```

This is intentional — it forces explicit configuration for deployment-critical values.

## Per-Source Interpolation

When you use [multi-file configs](Chapter_13.md), each file's `vars` block is interpolated independently before merging. File A's vars don't leak into File B's interpolation.

> **Tips & Tricks**
>
> - Use variables for anything that changes between environments: model IDs, API endpoints, log levels, session directories.
> - The `${VAR:-default}` pattern is your best friend for making configs self-contained — they work out of the box but can be customized via environment.
> - `vars` is removed after interpolation — it never reaches schema validation. So you can put anything in there, even nested dicts and lists (though string/number values are most common).
> - Want to see what resolved? Use `load_config()` instead of `load()` — it returns the validated `AppConfig` without starting anything.

---

[Next: Chapter 4 — YAML Anchors →](Chapter_04.md)
