# Chapter 1: The Basics — Your First Config

[← Back to Table of Contents](README.md)

---

A strands-compose config is a YAML file with a handful of top-level sections. The only truly **required** fields are `agents` (at least one) and `entry` (which agent or orchestration to call).

Here is the absolute minimum:

```yaml
agents:
  assistant:
    system_prompt: "You are a helpful assistant."

entry: assistant
```

That's it. One agent, one entry point. Load it in Python:

```python
from strands_compose import load

resolved = load("config.yaml")
result = resolved.entry("Hello!")
print(result)
```

`resolved.entry` is a plain `strands.Agent` — nothing wrapped, nothing magic. You can call it, inspect it, pass it around — it's the real deal.

## Root-Level Sections

Here is the full list of top-level keys you can put in a config file:

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `version` | string | No | Schema version. Only `"1"` is supported. Defaults to `"1"`. |
| `vars` | dict | No | Variable definitions for `${VAR}` interpolation. |
| `models` | dict | No | Named LLM model definitions. |
| `agents` | dict | **Yes** (at least one somewhere) | Named agent definitions. |
| `orchestrations` | dict | No | Named multi-agent orchestration definitions. |
| `mcp_servers` | dict | No | Named MCP server definitions (managed lifecycle). |
| `mcp_clients` | dict | No | Named MCP client connections. |
| `session_manager` | dict | No | Global session manager (inherited by all agents). |
| `entry` | string | **Yes** | Name of the agent or orchestration to use as the entry point. |
| `log_level` | string | No | Logging level for strands_compose. Default: `"WARNING"`. |

Sections marked as **dict** are name-keyed dictionaries — you pick the name, and it becomes the identifier:

```yaml
models:
  my_fast_model:    # <-- you chose this name
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0
```

The `x-` prefix is reserved for scratch-pad keys (YAML anchors) — they are **stripped** before validation and never reach the schema. More on that in [Chapter 4](Chapter_04.md).

## What About `vars`?

`vars` is special. It's consumed during interpolation and **removed** before schema validation. You will never see it in the final `AppConfig` object. It exists only to feed `${VAR}` references. Covered in [Chapter 3](Chapter_03.md).

> **Tips & Tricks**
>
> - You can omit `models` entirely. If an agent doesn't specify a `model`, strands uses its default (Bedrock with the default model). Handy for quick prototyping.
> - `entry` must reference something defined in either `agents` or `orchestrations`. If it doesn't, you'll get a clear error at load time.
> - Names follow the pattern `[a-zA-Z0-9_-]` and are limited to 64 characters. Spaces and special characters are auto-sanitized to underscores.

---

[Next: Chapter 2 — Models →](Chapter_02.md)
