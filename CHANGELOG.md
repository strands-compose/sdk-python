# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
## v0.11.2 (2026-09-24)

### Fix

- **renderers**: keep concurrent agent output in one block per agent (#85)

## v0.11.1 (2026-09-23)

### Fix

- **config**: load Python file specs living inside packages (#84)

## v0.11.0 (2026-08-15)

### BREAKING CHANGE

- Requires `strands-agents>=1.52.0`.
- MCP is client-side only. Removed `mcp_servers:` and `server:` on MCP clients, plus `MCPServerDef`, `create_mcp_server`, and `MCPLifecycle`. A server is either spawned as a stdio subprocess (`command:`) or already running remotely (`url:`).
- Removed `tool_labels:` on agents and the `tool_labels` argument on `EventPublisher` / `make_event_queue`. TOOL_START / TOOL_END events and the renderers now always report the real tool name.
- `load()` is the single entry point. Removed `resolve_infra`, `ResolvedInfra`, and `load_session`; models and MCP clients are built per call, making every `load()` a fully isolated session. `strands-compose load` is now synchronous.
- Delegate connections are wired through native `strands.Agent.as_tool` instead of a bespoke wrapper. `preserve_context: false` is rejected for a Swarm or Graph target, and rejected by strands for an agent with a session manager.

### Feat

- drop self-hosted mcp servers and tool labels overwrite (#81)
- **delegate**: wire agent connections through Agent.as_tool (#80)

### Fix

- **renderers**: render INTERRUPT events instead of dropping them silently
- **tools**: load directory tool specs recursively, skipping `_`- and `.`-prefixed path segments
- **orchestrations**: count a Swarm's or Graph's `entry_name` as a node reference so a nested orchestration used only as the entry is built before its parent
- **mcp**: correct transport auto-detection for `url:`
- **cli**: report the session provider in `check` for built-in providers

## v0.10.0 (2026-07-26)

### Feat

- **plugins**: add declarative agent plugin support (#75)
- **models**: add Anthropic provider support (#74)
- **event_publisher**: Include model data in AGENT_COMPLETE events (#71)

### Fix

- **renderers**: suppress empty ANSI renderer sections for whitespace-only events (#69)

## v0.9.0 (2026-06-22)

### Feat

- **tools**: add serialize_multiagent_result (#62)

### Fix

- **events**: rename error event data key from message to text (#63)

## v0.8.0 (2026-06-22)

### Feat

- **events**: make session id explicit in event stream (#61)

## v0.7.0 (2026-06-21)

### Feat

- **hooks**: include text and message in AGENT_COMPLETE event (#60)

## v0.6.0 (2026-06-20)

### BREAKING CHANGE

- Renamed `complete` event type to` agent_complete`. Any client, integration, or custom hook relying on the `complete` or `COMPLETE` event type must be updated to use `agent_complete` / `AGENT_COMPLETE` instead.

### Fix

- **manifest**: add delegate orchestration entry agent to agents collection

### Refactor

- **events**: rename complete event type to agent_complete

## v0.5.0 (2026-05-24)

### Feat

- **events**: add SESSION_START and SESSION_END lifecycle events (#47)

## v0.4.0 (2026-05-23)

### Feat

- **event_publisher**: Surface agent interrupts as stream events
- **converters**: replace native tool_calls deltas with completed details blocks (#45)

### Fix

- **session-manager**: eliminate session manager double-folder bug (#44)

## v0.3.0 (2026-05-20)

### Feat

- **tools**: preserve full message content across delegation boundary

## v0.2.0 (2026-04-12)

### Feat

- **renderers**: add `typewriter_delay` parameter to `AnsiRenderer` (#28)

## v0.1.2 (2026-03-27)

### Fix

- **tools**: support legacy strands module-based tool pattern (#14)
- add Windows path support (#13)
- align strands-agents version constraint in extras with main dependency (#10)

## v0.1.1 (2026-03-24)

### Fix

- use absolute URL for logo image in README (#8)

## v0.1.0 — 2026-03-23

Initial public release of **strands-compose** — declarative multi-agent orchestration for [strands-agents](https://github.com/strands-agents/sdk-python).

### Added

- **YAML-first configuration** — define models, agents, tools, hooks, MCP servers, and orchestration topology in a single YAML file
- **Full YAML power** — environment variable interpolation (`${VAR:-default}`), anchors (`&ref` / `*ref`), `x-` scratch-pad keys, and multi-file config merging
- **Multi-model support** — Bedrock, OpenAI, Ollama, Gemini; swap provider with one line
- **MCP servers & clients** — launch local Python servers, connect to remote HTTP endpoints, or spawn stdio subprocesses; lifecycle management with startup ordering, readiness polling, and graceful shutdown
- **Orchestration modes** — Delegate (agent-as-tool), Swarm (peer handoffs), Graph (DAG pipelines) — arbitrarily nestable
- **Event streaming** — unified async event queue across any orchestration depth (tokens, tool calls, handoffs, completions)
- **Session persistence** — file, S3, or Bedrock AgentCore Memory backends; agents remember across restarts
- **Custom agent factories** — plug in your own `Agent` subclass or factory via the `type:` key
- **Hooks** — lifecycle callbacks (`before_invoke`, `after_invoke`, etc.) declared in YAML and implemented in Python
- **`load()` API** — single entry point that resolves, validates, and wires the full agent system; returns plain `strands` objects with no wrappers

### Contributors

- [@galuszkm](https://github.com/galuszkm) — initial design and implementation
