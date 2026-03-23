# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
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
