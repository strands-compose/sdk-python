# strands-compose Examples

Each example is a self-contained folder with a `README.md`, `config.yaml`, and `main.py`.

| # | Folder | What it demonstrates |
|---|--------|----------------------|
| 01 | [01_minimal](./01_minimal/) | `load()` in one line — the simplest possible agent |
| 02 | [02_vars_and_anchors](./02_vars_and_anchors/) | Variables & YAML anchors — DRY configuration patterns |
| 03 | [03_tools](./03_tools/) | `tools:` list — auto-loading Python functions as agent tools |
| 04 | [04_session](./04_session/) | `session_manager:` — persistent memory across turns |
| 05 | [05_hooks](./05_hooks/) | `hooks:` — `MaxToolCallsGuard`, `ToolNameSanitizer`, and custom hooks |
| 06 | [06_mcp](./06_mcp/) | MCP — all three connection modes: local server (`mcp_servers:`), external URL (`url:`), stdio (`command:`) |
| 07 | [07_delegate](./07_delegate/) | `mode: delegate` — coordinator routes to specialist agents |
| 08 | [08_swarm](./08_swarm/) | `mode: swarm` — peer agents hand off autonomously |
| 09 | [09_graph](./09_graph/) | `mode: graph` — explicit DAG pipeline between agents |
| 10 | [10_nested](./10_nested/) | Nested orchestration — Swarm inside a Delegate |
| 11 | [11_multi_file_config](./11_multi_file_config/) | Split config across files — infrastructure in one YAML, agents in another |
| 12 | [12_streaming](./12_streaming/) | `wire_event_queue()` — stream every token, tool call, and completion live |
| 13 | [13_graph_conditions](./13_graph_conditions/) | Conditional graph edges — `condition:`, `reset_on_revisit`, `max_node_executions` |
| 14 | [14_agent_factory](./14_agent_factory/) | `type:` + `agent_kwargs:` — custom agent factory instead of default `Agent()` |

## Prerequisites

```bash
uv sync
```

Set `AWS_REGION` and valid Bedrock credentials before running.

The default model is `openai.gpt-oss-20b-1:0`; override per-directory with `MODEL=<model-id>`.

## Running an example

```bash
uv run python examples/01_minimal/main.py
```
