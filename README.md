<div align="center">
  <img src="https://raw.githubusercontent.com/strands-compose/sdk-python/main/docs/img/logo.png" width="180" alt="strands-compose">

  # Strands Compose

  **Declarative multi-agent orchestration for [strands-agents](https://github.com/strands-agents/harness-sdk) — wire entire agent systems with YAML**

  <p>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
    <a href="https://pypi.org/project/strands-compose/"><img src="https://img.shields.io/pypi/v/strands-compose.svg" alt="PyPI version"></a>
    <a href="https://github.com/strands-agents/harness-sdk"><img src="https://img.shields.io/badge/strands--agents-1.35.0+-green.svg" alt="Strands Agents"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License"></a>
  </p>
</div>

> [!IMPORTANT]
> Community project — not affiliated with AWS or the strands-agents team. Bugs here? [Open an issue](https://github.com/strands-compose/sdk-python/issues). Bugs in the underlying SDK? Head to [strands-agents](https://github.com/strands-agents/harness-sdk).

## What is this?

> **Think Docker Compose, but for AI agents**

[Strands](https://github.com/strands-agents/harness-sdk) is a powerful agent SDK. But once you have more than one agent, a few MCP servers, safety hooks, and shared models — you end up writing the same plumbing over and over. **strands-compose kills that boilerplate.**

You describe the shape of your agent system in YAML, and strands-compose resolves, validates, and starts everything — models, MCP servers & clients, hooks, tools, orchestration topology — as a live, fully wired multi-agent system.

```yaml
models:
  default:
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0

agents:
  researcher:
    model: default
    system_prompt: "You research topics."
    tools: [strands_tools.http_request]

  writer:
    model: default
    system_prompt: "You write reports."

  coordinator:
    model: default
    system_prompt: "Coordinate research and writing."

orchestrations:
  team_leader:
    mode: delegate
    entry_name: coordinator
    connections:
      - agent: researcher
        description: "Research a topic."
      - agent: writer
        description: "Write the report."

entry: team_leader
```

```python
from strands_compose import load

resolved = load("config.yaml")

result = resolved.entry("Write a report about quantum computing.")
print(result)
```

Three agents, orchestration wiring, model sharing — **zero plumbing code**.

**Already working with strands? Guess what — you already know strands-compose.** After `load()` resolves your YAML, what you get back are plain strands objects. Every agent **is** a `strands.Agent`. Every MCP client **is** a `strands.tools.mcp.MCPClient`. Every orchestrator **is** a `strands.multiagent.Swarm` or `Graph` or just `strands.Agent`. No wrappers, no subclasses, no magic. Just the real deal, fully wired and ready to go.

---

## See related projects

Strands Compose is an ecosystem that includes the following packages:

| Layer | Package | Who uses it |
|-------|---------|-------------|
| **Define the agents** | [**strands-compose**](https://github.com/strands-compose/sdk-python) | Developers |
| Run / deploy the agents | [strands-compose-agentcore](https://github.com/strands-compose/bedrock-agentcore) | Developers, operations |
|*Put the agents in front of people | [strands-compose-chat](https://github.com/strands-compose/chat-ui) | **End users** |

---

## Why this changes everything

Your entire agent network — models, prompts, tools, hooks, MCP servers, orchestration topology — captured in a single YAML file and maybe a few Python files for custom tools or hooks. That's it. That's your agent environment. Here's what that unlocks:

### 🔖 Version it

Push to Git. Tag it. Diff two versions and see exactly what changed. No more "I think someone changed the system prompt last Tuesday."

### 📦 Build a registry

A folder of YAML configs — one per agent environment. `production.yaml`, `staging.yaml`, `experiment-42.yaml`. Each is a complete, self-contained snapshot of an agent system. That's your agent environments registry — no platform needed.

### 🧪 Automate experiments

Your entire config is data, so you can *generate* it. Build 20 variations — different models, different prompts, different tool combinations — and run them all in CI. Point another strands-compose pipeline to analyze results compute metrics. You're benchmarking agent systems *with agent systems*.

### 🔁 Reproduce anything

A bug report comes in. You have the exact YAML config. Load it, replay it, debug it. No "works on my machine" — the config *is* the machine.

### CRAZY, right?!

---

## What's in the box

| Feature | What it does |
|---------|-------------|
| **YAML-first config** | Models, agents, tools, hooks, MCP, orchestrations — all in one file |
| **Full YAML power** | Variables (`${VAR:-default}`), anchors (`&ref` / `*ref`), `x-` scratch pads, multi-file merge |
| **Multi-model support** | Bedrock, Anthropic, OpenAI, Ollama, Gemini — swap with one line |
| **MCP servers & clients** | Launch local servers from Python files, connect to remote HTTP endpoints, or spawn stdio subprocesses |
| **MCP lifecycle management** | Startup ordering, readiness polling, graceful shutdown — servers before clients, always |
| **Orchestration modes** | Delegate (agent-as-tool), Swarm (peer handoffs), Graph (DAG pipelines) — arbitrarily nestable |
| **Event streaming** | Unified async event queue across any orchestration depth — tokens, tool calls, handoffs, completions |
| **Session persistence** | File, S3, or [Bedrock AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) — agents remember across restarts |
| **Custom agent factories** | Plug your own `Agent` subclass or factory via `type:` |
| **Deployment-agnostic** | Pure core library — no HTTP server, no deployment opinions baked in |

---

## Examples

Every example is a self-contained folder with a `README.md`, `config.yaml`, and `main.py`. Start from the top and work your way down — each one builds on concepts from the previous.

```bash
# Run any example
uv run python examples/01_minimal/main.py
```

| # | Example | What it shows |
|---|---------|---------------|
| 01 | [Minimal](examples/01_minimal/) | `load()` one-liner — the simplest possible agent |
| 02 | [Vars & Anchors](examples/02_vars_and_anchors/) | `${VAR:-default}` interpolation and YAML `&anchor` / `*alias` reuse |
| 03 | [Tools](examples/03_tools/) | `tools:` — auto-load `@tool` functions from Python files |
| 04 | [Session](examples/04_session/) | `session_manager:` — persistent memory across turns and restarts |
| 05 | [Hooks](examples/05_hooks/) | `hooks:` — `MaxToolCallsGuard`, `ToolNameSanitizer`, and custom hooks |
| 06 | [MCP](examples/06_mcp/) | All three MCP modes: local server, remote URL, stdio subprocess |
| 07 | [Delegate](examples/07_delegate/) | `mode: delegate` — coordinator routes work to specialist agents |
| 08 | [Swarm](examples/08_swarm/) | `mode: swarm` — peer agents hand off to each other autonomously |
| 09 | [Graph](examples/09_graph/) | `mode: graph` — deterministic DAG pipeline between agents |
| 10 | [Nested](examples/10_nested/) | Nested orchestration — Swarm inside a Delegate |
| 11 | [Multi-file](examples/11_multi_file_config/) | Split config across files — infra in one YAML, agents in another |
| 12 | [Streaming](examples/12_streaming/) | `wire_event_queue()` — stream every token, tool call, and handoff live |
| 13 | [Graph conditions](examples/13_graph_conditions/) | Conditional edges — `condition:`, `reset_on_revisit`, `max_node_executions` |
| 14 | [Agent factory](examples/14_agent_factory/) | `type:` + `agent_kwargs:` — custom agent factory instead of `Agent()` |

---

## Getting started

Install with [uv](https://docs.astral.sh/uv/):

```bash
uv add strands-compose                   # Bedrock (default)
```

Create a `config.yaml`:

```yaml
models:
  default:
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0

agents:
  assistant:
    model: default
    system_prompt: "You are a helpful assistant."

entry: assistant
```

Run it:

```python
from strands_compose import load

resolved = load("config.yaml")

with resolved.mcp_lifecycle:
    result = resolved.entry("Hello!")
    print(result)
```

---

## YAML superpowers

**strands-compose** gives you Docker Compose-style variable interpolation **plus** full YAML anchor/alias support. DRY configs that adapt to any environment:

```yaml
vars:
  MODEL: ${MODEL:-us.anthropic.claude-sonnet-4-6-v1:0}
  TONE:  ${TONE:-friendly}

x-base: &base_prompt |
  You are a ${TONE} assistant.
  Keep answers clear and concise.

x-hooks: &safety_hooks
  - type: strands_compose.hooks:MaxToolCallsGuard
    params: { max_calls: 15 }
  - type: strands_compose.hooks:ToolNameSanitizer

models:
  default:
    provider: bedrock
    model_id: ${MODEL}

agents:
  assistant:
    model: default
    system_prompt: *base_prompt
    hooks: *safety_hooks

entry: assistant
```

Override at runtime: `TONE=formal MODEL=us.anthropic.claude-sonnet-4-6-v1:0 python main.py`

Split large configs across files — models in one, agents in another, MCP in a third — and merge them with `load(["base.yaml", "agents.yaml"])`. Each file interpolates its own `vars:` independently, collections merge, and duplicates are caught.

---

## Multi-agent orchestration

**strands-compose** supports 3 orchestration modes from strands. They can be nested arbitrarily — a delegate target can be a swarm, a graph node can be a delegate.

### Delegate — agent as a tool

The coordinator calls sub-agents like tool functions. Best for hub-and-spoke patterns:

```yaml
orchestrations:
  team_leader:
    mode: delegate
    entry_name: coordinator  # Agent declared in `agents:`
    connections:
      - agent: researcher
        description: "Research the topic."
      - agent: writer
        description: "Write the report."
```

### Swarm — autonomous handoffs

Peer agents pass control to each other. No central coordinator — agents decide when to hand off:

```yaml
orchestrations:
  review_team:
    mode: swarm
    entry_name: drafter                     # Swarm entry - agent name
    agents: [drafter, reviewer, tech_lead]  # Agents declared in `agents:`
    max_handoffs: 10
```

### Graph — deterministic DAG pipeline

Agents execute in dependency order. Independent nodes run in parallel. Supports conditional edges:

```yaml
orchestrations:
  blog:
    mode: graph
    entry_name: writer               # Graph entry - agent name
    edges:                 # We use agent names to define edges
      - from: writer
        to: reviewer
      - from: reviewer
        to: writer
        condition: ./conditions.py:needs_revision
      - from: reviewer
        to: publisher
        condition: ./conditions.py:is_approved
```

### Nested orchestrations

Named orchestrations reference each other. A swarm becomes a delegate tool, a delegate becomes a graph node — compose them however you want:

```yaml
orchestrations:
  content_team:   # This swarm is plugged in as a tool for the team_leader
    mode: swarm
    entry_name: researcher
    agents: [researcher, writer, reviewer]

  team_leader:
    mode: delegate
    entry_name: coordinator
    connections:
      - agent: content_team     # Nested swarm as a delegate tool
        description: "Content creation team."
      - agent: qa_bot           # Nested agent as a delegate tool
        description: "Quality assurance."

entry: team_leader
```

**strands-compose** topologically sorts all orchestrations, builds inner ones first, then wires them as tools or nodes for outer ones. Circular dependencies are caught at load time.

---

## Streaming-ready by design

One call — `resolved.wire_event_queue()` — silently injects an **`EventPublisher`** hook into every agent across your entire system, regardless of topology. Delegate, Swarm, Graph, nested three levels deep — all events funnel into one async queue. No per-agent wiring, no topology-specific plumbing.

**For the best local dev experience — use the `dev` CLI from [strands-compose-agentcore](https://github.com/strands-compose/bedrock-agentcore).** Or see [example 12](examples/12_streaming/) for pure strands-compose solution.

Every event carries `{type, agent_name, timestamp, data}` — uniform across all agents and orchestration modes:

**Single-agent events**

| Type | When |
|------|------|
| `agent_start` | Agent began processing |
| `token` | A chunk of generated text |
| `reasoning` | Model's thinking output |
| `tool_start` | Agent is calling a tool |
| `tool_end` | Tool returned a result |
| `agent_complete` | Agent finished processing |
| `error` | Something went wrong |

**Multi-agent events** (orchestrations)

| Type | When |
|------|------|
| `multiagent_start` | Orchestration started |
| `node_start` | A node in the graph/swarm started |
| `handoff` | Agent handing off to another |
| `node_stop` | A node finished |
| `multiagent_complete` | Orchestration finished |

**Session-level events**

| Type | When |
|------|------|
| `session_start` | First event of a turn — includes full wired topology manifest |
| `session_end` | Last event of a turn — includes final response text and full result |

This is a standard SSE design — uniform JSON events ready to pipe straight into any modern web service, log aggregator, or real-time frontend. The built-in `AnsiRenderer` gives you coloured terminal output immediately: agent names, tool calls, reasoning traces, handoffs — all streaming live.

---

## Developer setup

```bash
git clone https://github.com/strands-compose/sdk-python
cd sdk-python
uv run just install      # install deps + wire git hooks (run once after clone)

uv run just check        # lint + type check + security scan
uv run just test         # pytest with coverage
uv run just format       # auto-format (Ruff)
```

> Re-install hooks after a fresh clone or if hooks stop running: `uv run just install-hooks`

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution guide and [CHANGELOG.md](CHANGELOG.md) for release history.
