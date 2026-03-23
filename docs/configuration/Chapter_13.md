# Chapter 13: Multi-File Configs — Splitting and Merging

[← Back to Table of Contents](README.md) | [← Previous: Nested Orchestrations](Chapter_12.md)

---

Large configs can be split across multiple files. Pass a list to `load()` and they're merged:

```python
from strands_compose import load

resolved = load(["base.yaml", "agents.yaml", "mcp.yaml"])
```

## Merge Rules

**Collection sections** (dicts) are merged across files:

- `models` — merged
- `agents` — merged
- `orchestrations` — merged
- `mcp_servers` — merged
- `mcp_clients` — merged

**Singleton fields** use last-wins semantics:

- `entry` — last file's value wins
- `session_manager` — last file's value wins
- `log_level` — last file's value wins
- `version` — last file's value wins

## Duplicate Detection

If two files define the same name in the same collection section, loading fails:

```yaml
# file_a.yaml
agents:
  helper:
    system_prompt: "I help."

# file_b.yaml
agents:
  helper:                  # Duplicate!
    system_prompt: "I also help."
```

```
ValueError: Duplicate names in 'agents' across config sources: ['helper']
```

## Per-File Variable Interpolation

Each file's `vars` block is interpolated independently *before* merging. This means File A's vars don't affect File B:

```yaml
# base.yaml
vars:
  MODEL: us.anthropic.claude-sonnet-4-6-v1:0
models:
  default:
    provider: bedrock
    model_id: ${MODEL}         # Resolves from base.yaml's vars

# agents.yaml
vars:
  TONE: friendly               # This is agents.yaml's own vars
agents:
  assistant:
    model: default
    system_prompt: "You are ${TONE}."
entry: assistant
```

## Typical Split Patterns

**Infrastructure + Application**:
```
base.yaml     — vars, models, mcp_servers, mcp_clients, session_manager
agents.yaml   — agents, orchestrations, entry
```

**Environment Layering**:
```
base.yaml        — shared models, shared agents
production.yaml  — production model IDs, production entry
staging.yaml     — staging model IDs, staging entry
```

**Team-Based**:
```
models.yaml       — all model definitions
research.yaml     — researcher agents + orchestrations
content.yaml      — writer/editor agents + orchestrations
main.yaml         — coordinator agent, top-level orchestration, entry
```

## Neither File Needs to Be Complete

Individual files don't need to be valid on their own. `base.yaml` can define models without agents or entry. `agents.yaml` can reference models it doesn't define. The merged result must be valid — individual files don't.

> **Tips & Tricks**
>
> - Use multi-file configs when your single file exceeds ~200 lines. It makes diffs cleaner and team collaboration easier.
> - The `entry` field should typically go in the "application" file, not the "infrastructure" file — it's the most likely to change between use cases.
> - File paths for tools/hooks/servers are resolved relative to the file they appear in. If `agents.yaml` says `tools: [./tools.py]`, it looks for `tools.py` next to `agents.yaml`.

---

[Next: Chapter 14 — Agent Factories →](Chapter_14.md)
