---
name: library-development
description: Build and extend strands-compose — the declarative YAML to strands resolution library in src/strands_compose. Use when adding or editing config schema, loaders, resolvers, orchestration builders, model/mcp/tool/hook resolution, streaming, manifests, or the CLI. Library source only; not tests, examples, or docs.
metadata:
  area: library
  stack: python,pydantic-v2,strands-agents,pyyaml,mcp
---

# Library Development

Rules for the **strands-compose library** in `src/strands_compose/`
(Python ≥ 3.11 + Pydantic v2 + strands-agents + PyYAML + MCP). They describe
the **mental model and conventions**, not the current set of files — sections,
providers, and orchestration modes come and go, the shape stays.

strands-compose does exactly one thing: **read YAML and hand back fully wired,
plain `strands` objects — no wrappers, no subclasses.** Everything agent-,
model-, session-, tool-, or MCP-related is provided by strands. Before building
anything that touches those, check the installed SDK
(`.venv/lib/python*/site-packages/strands/`) and use what it provides rather
than re-implementing it. When in doubt about upstream APIs, use the
`strands-api-lookup` skill.

Before creating anything new, read a sibling that plays the same role and copy
its shape. Matching the existing pattern matters more than any rule below. See
`references/project-map.md` for where each role lives and what to read first —
load it whenever you are unsure where something goes.

---

## Core Principles — NON-NEGOTIABLE

1. **Strands-first** — if strands provides it, import and use it directly; never re-implement it. This library is a translator, not a framework.
2. **Thin wrapper** — translate YAML to strands objects, then get out of the way. Return plain `Agent` / `Swarm` / `Graph` / `Model` / `MCPClient`, never a subclass or proxy.
3. **The pipeline flows one way** — text -> dict -> validated schema -> live objects. Never resolve during parsing; never parse during resolution (see The Pipeline).
4. **Explicit over implicit** — no auto-registration, no global singletons, no hidden state. Every object is wired by hand and passed as an argument.
5. **Single responsibility** — each module does one thing; one resolver per config concept, one builder per orchestration mode.
6. **Composition over inheritance** — small functions and focused modules that compose. The only base classes are the strands-facing ones (`MCPServer`, `StreamConverter`, `HookProvider`).
7. **Smallest reasonable change** — don't refactor unrelated code to land a feature.

---

## The Pipeline — the central mental model

Everything the library does is one directional flow. `load()` is the whole
story end to end:

```
load(config)
├─ load_config(config) ─────────────────────────────► AppConfig   (validated, pure data)
│   ├─ parse_single_source   read/inline YAML · strip x-* anchors ·
│   │                        interpolate ${VAR:-default} · rewrite relative paths -> absolute
│   ├─ sanitize_collection_keys   names -> [a-zA-Z0-9_-]; update internal refs
│   ├─ merge_raw_configs          multi-source merge (duplicate names raise)
│   ├─ normalize                  schema-version migration hook
│   ├─ AppConfig.model_validate   Pydantic schema validation
│   └─ validate_references        every model/mcp/node reference must exist
├─ resolve_infra(config) ───────────────────────────► ResolvedInfra   (COLD — nothing started)
│      models · mcp servers · mcp clients · cold MCPLifecycle
├─ infra.mcp_lifecycle.start()   servers must be up before agents (Agent.__init__ auto-starts clients)
└─ load_session(config, infra) ─────────────────────► ResolvedConfig   (live agents, entry, lifecycle)
       resolve_agents · resolve_orchestrations · pick entry
```

Two hard boundaries define where code goes:

- **Parse vs resolve.** `load_config` produces pure validated data (`AppConfig`
  and its `*Def` models). `resolve_infra` / `load_session` turn that data into
  live strands objects. Dict-munging, YAML, interpolation, and merging belong to
  the parse side (`config/loaders/`); constructing strands objects belongs to
  the resolve side (`config/resolvers/`). Never mix them.
- **Infra vs session.** `resolve_infra` builds process-lifetime, shareable
  things (models, MCP servers/clients, the lifecycle) with **no session
  managers** and a cold lifecycle. `load_session` builds per-session things
  (agents, orchestrations, session managers). This split is what lets one
  process serve many isolated sessions — one `resolve_infra`, many
  `load_session` calls. Never store a session manager on `ResolvedInfra`.

---

## The Resolver Contract — the shape every `resolve_*` shares

The `config/resolvers/` package is the heart of the library, and every resolver
is the same shape. Learn it once, apply it everywhere. A resolver takes a `*Def`
Pydantic model and returns a live strands object:

1. **Dispatch built-in vs custom.** Named built-ins (`"bedrock"`, `"file"`,
   `"swarm"`, …) route to a dedicated factory. Anything else is treated as an
   **import spec** and loaded via `load_object` — this is the single, unified
   entry point for every `module.path:Name` or `./file.py:Name` string in the
   whole library (agent factories, model classes, hooks, session managers, MCP
   server factories, graph-edge conditions). Never write your own import logic.
2. **Validate the result type.** After constructing a custom object, assert it
   is the expected strands base (`isinstance` / `issubclass`) and raise
   `TypeError` with context if not. A resolver must never return the wrong kind
   of object.
3. **Fail fast with a contextual message.** Unknown provider -> `ValueError`
   listing the supported set. Missing required param -> `ValueError` naming it.

Two structural rules layered on top:

- **`build_agent_from_def` is the canonical agent constructor.** Both
  `resolve_agents` and the delegate builder go through it. Delegate mode
  **forks a new agent** from an entry agent's blueprint (`model_copy` + extra
  tools/hooks) — it **never mutates** the original agent.
- **Session managers resolve through one uniform leaf chain**
  (`resolve_leaf_session_manager`): per-leaf override -> explicit opt-out
  (`session_manager: ~`) -> global default -> `None`. Agents and orchestrations
  use it identically; the effective `session_id` is threaded down from
  `load_session`.

---

## The Schema is the floor — keep it pure

`config/schema.py` holds only Pydantic `*Def` models. It **imports nothing
application-specific and no strands runtime types** — no `Agent`, no
`MCPClient`, no resolvers. It is pure data + validation, and it is the one place
that catches user mistakes at parse time with clear messages.

- Discriminated unions for closed sets (`OrchestrationDef` on `mode`,
  session-manager descriptors on `provider`).
- Cross-field / cross-section rules live in `@model_validator(mode="after")`
  (entry must exist, no name collisions across `JOINT_NAMESPACES`).
- Reference-bearing orchestration fields declare a `reference_fields()`
  descriptor so key-sanitization can rewrite them generically.
- **Adding a new config section?** Add the field to `AppConfig`, then update
  `COLLECTION_KEYS` (if it's a merged named-dict collection) and
  `JOINT_NAMESPACES` (if it shares a name namespace). This is called out in the
  schema itself — honour it.

---

## Dependency Direction (read this twice)

Imports flow one way. Inner layers never reach outward.

```
loaders/  ──────►  schema.py  ◄──────  resolvers/  ──────►  strands objects
(I/O, dicts)       (pure Pydantic)     (Def -> object)       models.py · mcp/ · tools/ · hooks/
                                          │
                                          └──►  utils.load_object  (the one import resolver)

foundation, imported freely:  types.py · exceptions.py · wire.py · manifest.py
```

- `schema.py` depends on Pydantic only — the floor.
- `loaders/` do text I/O and dict transforms, import `schema`, and **never
  import resolvers**. Parsing must not construct live objects.
- `resolvers/` import `schema`, strands, and the subsystem builders
  (`models.py`, `mcp/`, `tools/`, `hooks/`, `utils.load_object`). They turn a
  `*Def` into a live object and nothing else.
- `wire.py`, `manifest.py`, `types.py`, `exceptions.py` are foundation — they
  operate on live strands objects or shared types and import nothing from the
  config layer.
- A loader importing a resolver, or `schema.py` importing `Agent`, is a design
  smell — stop and move the code to its layer.

---

## Streaming, Manifest, Lifecycle — the runtime edges

- **Streaming is uniform.** `EventPublisher` (a `HookProvider`) is the single
  translator from strands hook events -> typed `StreamEvent`. `make_event_queue`
  attaches it to every agent and orchestrator; `EventQueue` hides the
  end-of-stream sentinel and brackets each run with `SESSION_START` /
  `SESSION_END`. New event kinds are added to `EventType` and emitted from
  `EventPublisher` — not invented ad hoc elsewhere.
- **The manifest is pure introspection.** `build_manifest` reads live
  `Agent` / `Swarm` / `Graph` / `SessionManager` objects and produces a
  `SessionManifest`. No I/O, no mutation. It is decoupled from the YAML schema
  on purpose — it describes what was *wired*, not what was *configured*.
- **MCP lifecycle is ordered and idempotent.** Servers start (and become ready)
  before clients connect; clients stop before servers. `start()` is idempotent
  because `Agent.__init__` also auto-starts clients — the context manager is
  still required for graceful shutdown.
- **Optional providers import lazily inside the function** that needs them
  (`bedrock`, `ollama`, `openai`, `gemini`, `agentcore`), each raising a clear
  `ImportError` pointing at the extra (`pip install strands-compose[openai]`).
  This is the one sanctioned use of function-local imports; keep it.

---

## Python Conventions

- **`from __future__ import annotations`** at the top of every module.
- **Module docstring** describing the module's single responsibility.
- **Fully typed signatures** — every function/method (public *and* private)
  declares parameter and return types. Use `X | None`, `X | Y`, `list`, `dict`,
  `tuple` — never `Optional`, `Union`, `List`, `Dict`.
- **Google-style docstrings** on every public class, function, and method, with
  accurate `Args:` / `Returns:` / `Raises:`. **Class docstrings go on
  `__init__`**, not the class body (Pydantic `*Def` models are the exception —
  a short body docstring documenting the config surface is fine).
- **Early returns** — handle edge cases first; keep nesting ≤ 3 levels.
- **Raise specific exceptions** (`ValueError`, `KeyError`, `TypeError`,
  `RuntimeError`, or a `ConfigurationError` subclass) with a contextual message.
  When re-raising, chain with `raise … from exc` (or `from None` to suppress a
  noisy upstream trace, as the loaders do for Pydantic/YAML errors).
- **Never swallow exceptions silently**, no bare `except:`. The sanctioned broad
  catch is best-effort cleanup/shutdown (e.g. `MCPLifecycle.stop`): catch
  `Exception`, log with `exc_info=True`, and continue.
- **Return copies from properties** exposing mutable state:
  `return dict(self._servers)`.
- **Naming:** `PascalCase` classes · `snake_case` functions/methods ·
  `UPPER_SNAKE_CASE` constants · `_prefix` for private. No abbreviations in the
  public API. Booleans read as `is_` / `has_` / `enable_`. Don't shadow builtins.
- **`__all__` only in `__init__.py`** — it is the single source of truth for a
  package's public surface. The top-level `strands_compose/__init__.py` is the
  public API; consumers import from there, never from submodules.
- **Import order** stdlib -> third-party -> local (ruff-enforced, autofixed).
- Run modules with `uv run python …`, never bare `python`.

---

## Logging

One module-level logger: `logger = logging.getLogger(__name__)`. Never
`print()` for diagnostics (the CLI's user-facing output via `print` is the
deliberate exception, marked `# noqa: T201`).

Use `%s` interpolation with structured field-value pairs — never f-strings:

```python
logger.info("model=<%s>, provider=<%s> | resolved model", name, provider)
logger.warning("server=<%s> | failed to stop MCP server", name, exc_info=True)
```

- Field-value pairs first (`key=<value>`, comma-separated), human-readable
  message after ` | `, `<>` around values, lowercase, no trailing punctuation.
- `%s` format args, not f-strings (lazy evaluation, and it's a hard rule).

---

## Errors & Exceptions

- Config-time failures raise a `ConfigurationError` subclass from
  `exceptions.py` (`SchemaValidationError`, `UnresolvedReferenceError`,
  `CircularDependencyError`, `ImportResolutionError`). All subclass `ValueError`,
  so callers catching `ValueError` still work.
- Error messages are for humans debugging YAML: state what's wrong, then what's
  available or how to fix it (`f"…\nAvailable: {sorted(names)}"`).
- `cli_errors()` is **CLI-only** — it calls `sys.exit()`. Never use it in
  server/ASGI code; catch exceptions directly there.

---

## Adding to the Project — Checklist

1. **Decide which side of the pipeline it's on** — parsing (`loaders/`),
   schema (`schema.py`), or resolution (`resolvers/` + a subsystem). Unsure ->
   `references/project-map.md`.
2. **Read a sibling first.** Open the existing resolver / builder / loader of
   the same role and mirror its shape, docstrings, and error style.
3. **New config surface?** Add/extend the `*Def` in `schema.py` (keep it pure),
   add a `@model_validator` for cross-field rules, and update `COLLECTION_KEYS`
   / `JOINT_NAMESPACES` if it's a new section.
4. **New live object?** Write a `resolve_*` following the Resolver Contract —
   dispatch built-in vs `load_object`, validate the result type, fail fast.
5. **Reuse `load_object`** for any import-spec string. Never re-implement import
   or file-loading logic.
6. **New event kind?** Add to `EventType` and emit it from `EventPublisher`.
7. **New optional dependency?** Import it lazily inside the function, raise a
   clear `ImportError` pointing at the extra, and add the extra to
   `pyproject.toml`.
8. **Verify** before declaring done — see Verify.

---

## Verify

Run from the repository root (use the `check-and-test` skill for detail):

```bash
uv run just check    # ruff format-check + ruff lint + ty type-check + bandit
uv run just test     # pytest with coverage gate (≥ 70%)
```

`just check` is the gate; it must pass before a change is done. If it fails,
`uv run just format` first, then re-run. Do **not** start a long-running MCP
server or the CLI `load` command to "verify" — rely on `check` and `test`.

---

## Things NOT to Do

- Don't re-implement what strands provides — check the installed SDK first, and
  return plain strands objects (no wrappers, no subclasses).
- Don't construct live objects during parsing, or munge raw dicts during
  resolution — respect the parse/resolve boundary.
- Don't import a resolver from a loader, or `Agent`/`MCPClient` from
  `schema.py` — respect the one-way dependency flow; keep the schema pure.
- Don't store a session manager on `ResolvedInfra`, or blur the infra/session
  split.
- Don't write bespoke import logic — route every `module:Name` / `./file.py:Name`
  spec through `load_object`.
- Don't mutate an existing agent to build an orchestration — fork a new one from
  the blueprint.
- Don't add a config section without updating `COLLECTION_KEYS` /
  `JOINT_NAMESPACES` as the schema instructs.
- Don't use `Optional[X]` / `Union` / `List` / `Dict`, leave a signature
  untyped, or shadow a builtin.
- Don't `print()` for diagnostics (CLI output excepted), and don't use f-strings
  inside `logger.*` calls — use `%s` with field-value pairs.
- Don't swallow exceptions silently or use bare `except:`; the only broad catch
  is logged best-effort cleanup.
- Don't add `__all__` outside `__init__.py`; don't import library internals from
  submodules — use the top-level public API.
- Don't hardcode secrets; don't use `eval`/`exec`, `pickle` on untrusted data,
  or `subprocess(shell=True)`.
- Don't add files or folders outside the scope of the task.
- Don't leave broken or commented-out code; if you find something broken in the
  area you're working, fix it.
- Comments explain **what** and **why**, never **when** or **how it changed**.
