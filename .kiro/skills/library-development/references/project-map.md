# Library Project Map

Navigation aid for `src/strands_compose/`. Exact file names drift over time —
trust the **roles** and the "read first" pointers more than any single name.
When in doubt, follow the pipeline: a config concept has a `*Def` in
`schema.py`, a `resolve_*` in `resolvers/`, and (if it builds a strands object)
a factory in a subsystem package.

## Layout

```
src/strands_compose/
├── __init__.py          # PUBLIC API — load, load_config, ResolvedConfig,
│                        #   AppConfig, EventQueue, StreamEvent, hooks, renderers, …
├── models.py            # model provider factory: create_model() → Bedrock/Ollama/OpenAI/Gemini
├── types.py             # Node alias · EventType · StreamEvent · SessionManifest family (Pydantic)
├── exceptions.py        # ConfigurationError hierarchy (all subclass ValueError)
├── utils.py             # load_object() — THE import resolver · load_module_from_file · cli_errors
├── wire.py              # EventQueue + make_event_queue — streaming plumbing (SESSION_START/END)
├── manifest.py          # build_manifest(): live objects → SessionManifest (pure introspection)
├── cli.py               # `strands-compose check` / `load` sub-commands
├── config/
│   ├── schema.py        # PURE Pydantic *Def models · AppConfig · COLLECTION_KEYS · JOINT_NAMESPACES
│   ├── interpolation.py # ${VAR:-default} interpolation + x-* anchor stripping (two-pass vars)
│   ├── loaders/
│   │   ├── loaders.py       # load / load_config — THE pipeline entry points
│   │   ├── helpers.py       # parse source · sanitize keys · rewrite relative paths · merge sources
│   │   └── validators.py    # validate_references — cross-reference checks before resolution
│   └── resolvers/           # *Def → live strands object (the Resolver Contract)
│       ├── config.py            # ResolvedConfig (+ wire_event_queue)
│       ├── agents.py            # build_agent_from_def (canonical) · resolve_agents
│       ├── models.py            # resolve_model — built-in provider or custom import
│       ├── mcp.py               # resolve_mcp_client / resolve_tools
│       ├── hooks.py             # resolve_hook / resolve_hook_entry
│       ├── plugins.py           # resolve_plugin / resolve_plugin_entry
│       ├── session_manager.py   # resolve_session_manager · resolve_leaf_session_manager (leaf chain)
│       ├── conversation_manager.py
│       └── orchestrations/
│           ├── planner.py       # topological_sort · collect_node_refs (cycle detection)
│           └── builders.py      # OrchestrationBuilder · build_delegate/swarm/graph
├── mcp/
│   ├── client.py        # create_mcp_client() — returns strands MCPClient (url= or command=)
│   └── transports.py    # stdio / sse / streamable_http transport factories + MCP_TRANSPORT
├── tools/
│   ├── loaders.py       # resolve_tool_spec(s) — module/file/dir → AgentTool
│   ├── extractors.py    # extract_last_message · serialize_multiagent_result
│   └── wrappers.py      # multiagent_as_tool — wrap a Swarm/Graph as a delegate tool
├── hooks/               # reusable HookProvider implementations
│   ├── event_publisher.py    # EventPublisher — strands hook events → StreamEvent (the key one)
│   ├── stop_guard.py         # StopGuard / MultiAgentStopGuard — external cancel signal
│   ├── max_calls_guard.py    # MaxToolCallsGuard — tool-call circuit breaker
│   └── tool_name_sanitizer.py# ToolNameSanitizer — repair model-mangled tool names
└── renderers/           # terminal output (base ABC · ansi)
```

## Where to read first, by task

| Task | Read these first |
|------|------------------|
| Understand the whole flow | `config/loaders/loaders.py` — `load()` is the entire pipeline, `load_config()` is its parse half |
| Add / change a config field | `config/schema.py` (the matching `*Def`), then its `resolve_*` |
| Write a new `resolve_*` | `config/resolvers/models.py` (simplest built-in-vs-import example) + `hooks.py` |
| Agent construction | `config/resolvers/agents.py` — `build_agent_from_def` (the canonical path) |
| Session managers / the leaf chain | `config/resolvers/session_manager.py` — `resolve_leaf_session_manager` |
| A new orchestration mode | `config/resolvers/orchestrations/builders.py` + `schema.py` orchestration defs |
| Orchestration ordering / cycles | `config/resolvers/orchestrations/planner.py` |
| YAML parsing / interpolation / merge | `config/loaders/helpers.py`, `config/interpolation.py` |
| Cross-reference validation | `config/loaders/validators.py` |
| An import-spec string (`module:Name`) | `utils.py` — `load_object` (never re-implement) |
| Model providers | `models.py` — `create_model` + `PROVIDERS` |
| MCP client / transport | `mcp/client.py`, `mcp/transports.py` |
| Tool loading from spec strings | `tools/loaders.py` — `resolve_tool_spec` |
| Delegation (node as a tool) | `tools/wrappers.py` |
| Streaming events | `hooks/event_publisher.py` + `wire.py` (`EventQueue`, `make_event_queue`) |
| A new event type | `types.py` (`EventType`) then `hooks/event_publisher.py` |
| Session topology / introspection | `manifest.py` + `types.py` (`SessionManifest`) |
| CLI behaviour | `cli.py` — `check` (parse only) and `load` (build everything) |

## Invariants observed in the tree

- **One `resolve_*` per config concept**, all sharing the Resolver Contract:
  dispatch built-in name vs `load_object` import spec, then validate the result
  type (`isinstance`/`issubclass`) and raise `TypeError`/`ValueError` with an
  actionable message.
- **`schema.py` is pure** — Pydantic only, no strands runtime imports. It is the
  parse/resolve floor.
- **`load_object` is the sole import resolver** for `module.path:Name` and
  `./file.py:Name` specs, everywhere.
- **`build_agent_from_def` is the only agent constructor**; delegate mode forks
  a new agent from a blueprint via `model_copy`, never mutating the original.
- **`load()` is the single resolution entry point**, and one call is one
  session. It accepts an `AppConfig` so a server can parse once with
  `load_config()` and resolve per session. There is no shared-infrastructure
  phase.
- **Optional providers import lazily** inside the resolving function, each with
  an `ImportError` naming the extra.
- **`__all__` lives only in `__init__.py`**; the top-level package is the public
  API consumers import from.

## Config surface (what the YAML author writes)

`AppConfig` (root): `version` · `models` · `mcp_clients` ·
`agents` · `session_manager` · `orchestrations` · `entry` (required) ·
`log_level`. Merged collection sections are `COLLECTION_KEYS`; `agents` and
`orchestrations` share one name namespace (`JOINT_NAMESPACES`). Orchestration
`mode` ∈ {`delegate`, `swarm`, `graph`} (discriminated union). See
`examples/` (numbered 01–15) for a worked config per feature and `docs/configuration/`
for the chapter-by-chapter reference.

## Stack notes

- **Python ≥ 3.11** (ruff/ty target 3.13). Runtime deps: `strands-agents`
  (>=1.52.0,<2), `pydantic` v2, `pyyaml`, `mcp`. Optional extras:
  `agentcore-memory`, `ollama`, `openai`, `gemini`, `anthropic`.
- **MCP is client-side only.** A server is either spawned by the client as a
  subprocess (`command:`, stdio) or already running elsewhere (`url:`,
  `streamable-http` / `sse`). We never host one, and strands owns client
  lifetime via consumer reference counting.
- **Tooling:** `ruff` (lint + format), `ty` (type check), `bandit` (security),
  `pytest` + `pytest-asyncio` + coverage — orchestrated through `just`, run via
  `uv run just …`.
- **Packaging:** hatchling builds `src/strands_compose`; console script
  `strands-compose = strands_compose.cli:main`.
