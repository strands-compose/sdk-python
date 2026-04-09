# 11 — Multi-File Config

> Split one config across multiple YAML files — each file owns one concern.

## What this shows

- `load(["base.yaml", "agents.yaml"])` — pass a list and strands-compose merges them
- Neither file is complete on its own; together they form a runnable config
- Agents in `agents.yaml` reference models defined in `base.yaml` — cross-file references just work
- `vars:` are scoped per file — each source resolves its own variables independently

## How it works

```
load(["base.yaml", "agents.yaml"])
          ↓               ↓
    vars + models    agents + entry
        └─────────┬─────────┘
             merged config
```

**Merging rules:**
- **Collections** (`agents`, `models`, `mcp_servers`, etc.) are **combined** — each file
  contributes unique names
- **Singletons** (`entry`, `log_level`) use **last-wins** — the last file to define it wins
- **Duplicate names** across files raise `ValueError` — intentional, not a bug

| File | Contents | Standalone? |
|------|----------|-------------|
| `base.yaml` | `vars`, `models` | ✗ no agents, no entry |
| `agents.yaml` | `agents`, `entry` | ✗ no models defined |
| both together | complete config | ✓ runnable |

## Good to know

**Infra / app separation.** One team owns `base.yaml` (models, MCP servers), another
owns `agents.yaml` (agent definitions). Swap `base.yaml` per environment without
touching agent logic.

**Variables are file-scoped.** `${MODEL}` in `base.yaml` resolves from `base.yaml`'s
`vars:` block (or env). It won't see variables defined in `agents.yaml`.

**YAML anchors are file-scoped too.** An anchor in `base.yaml` can't be referenced
from `agents.yaml`. For shared blocks across files, use variables instead.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
# Linux / macOS
uv run python examples/11_multi_file_config/main.py

# Override the model
MODEL=us.anthropic.claude-sonnet-4-6-v1:0 uv run python examples/11_multi_file_config/main.py

# Windows PowerShell
uv run python examples/11_multi_file_config/main.py

# Override the model
$env:MODEL="us.anthropic.claude-sonnet-4-6-v1:0"; uv run python examples/11_multi_file_config/main.py
```

## Try these prompts

- `What is the difference between concurrency and parallelism?`
- `Explain Python's GIL in one paragraph.`
- `What are the SOLID principles?`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
