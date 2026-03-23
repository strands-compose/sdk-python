# Chapter 17: The Loading Pipeline — What Happens Under the Hood

[← Back to Table of Contents](README.md) | [← Previous: Name Sanitization](Chapter_16.md)

---

When you call `load("config.yaml")`, here's exactly what happens:

## Step 1: Parse Sources

Each config source (file path or raw YAML string) is parsed with `yaml.safe_load()`. `Path` objects are always treated as files. Strings are files if the path exists on disk, otherwise parsed as inline YAML.

## Step 2: Strip Anchors and Interpolate Variables

For each source independently:
1. Extract and remove the `vars` block
2. Strip `x-*` keys (YAML anchor scratch pads)
3. Interpolate `${VAR}` references using `vars` + environment

## Step 3: Rewrite Relative Paths

All filesystem-based specs (`./file.py:func`, `./tools/`) are rewritten to absolute paths anchored to the config file's directory. This ensures the config works regardless of the working directory.

## Step 4: Sanitize Collection Keys

Names in all collection sections are sanitized to `[a-zA-Z0-9_-]`. Cross-references are updated automatically.

## Step 5: Merge (If Multi-File)

Collection sections are combined, duplicate names detected, singleton fields use last-wins.

## Step 6: Validate Against Schema

The merged dict is validated against Pydantic models. Invalid fields, missing required values, wrong types — all caught here with clear error messages.

## Step 7: Validate References

Cross-references are checked:
- Agent `model` references → must exist in `models`
- Agent `mcp` references → must exist in `mcp_clients`
- MCP client `server` references → must exist in `mcp_servers`
- Orchestration agent references → must exist in `agents` or `orchestrations`

## Step 8: Resolve Infrastructure

Models, MCP servers, MCP clients, and session managers are created as Python objects. Nothing is started yet.

## Step 9: Start MCP Lifecycle

MCP servers are started in background threads. The pipeline waits for all servers to be ready (TCP port check). This happens **before** agent creation because `Agent.__init__` auto-starts MCP clients which need running servers.

## Step 10: Create Agents

Each agent definition is resolved: model looked up, tools loaded, hooks instantiated, MCP clients attached, session manager wired. Each agent is a fresh `strands.Agent` instance.

## Step 11: Wire Orchestrations

Orchestrations are topologically sorted and built in dependency order. Inner orchestrations first, outer orchestrations reference the already-built inner ones.

## Step 12: Return ResolvedConfig

The final `ResolvedConfig` has:
- `agents` — dict of all agents by name
- `orchestrators` — dict of all built orchestrations by name
- `entry` — the entry point (Agent, Swarm, or Graph)
- `mcp_lifecycle` — for managing shutdown

## Advanced Topic: `load()` vs `load_config()` + `resolve_infra()` + `load_session()`

Most users only need:

```python
from strands_compose import load

resolved = load("config.yaml")
```

That one call runs the whole pipeline:

1. Parse YAML
2. Interpolate variables
3. Sanitize names
4. Merge files
5. Validate schema + references
6. Resolve infrastructure
7. Start MCP lifecycle
8. Create agents and orchestrations

But strands-compose also exposes the lower-level split because **config parsing** and **session creation** are not always the same thing.

### What counts as "config"?

`load_config()` returns a validated `AppConfig` — just structured data.

At this point, nothing is started and no live strands objects exist yet:

- no `Agent` instances
- no orchestration objects
- no started MCP servers
- no connected MCP clients

This step is useful when you want to parse and validate once at process startup, fail fast on bad YAML, and keep the validated config around.

### What counts as "infrastructure"?

`resolve_infra(app_config)` turns the validated config into the shared runtime pieces:

- resolved model objects
- resolved MCP server objects
- resolved MCP client objects
- a cold `mcp_lifecycle`
- the global session manager (if configured)

Important nuance: **resolved** does not mean **started**.

After `resolve_infra()`:

- MCP servers exist as Python objects, but are not running yet
- MCP clients exist as Python objects, but are not connected yet
- agents still do not exist
- orchestrations still do not exist

You then start the shared MCP runtime explicitly:

```python
from strands_compose.config import load_config, resolve_infra

app_config = load_config("config.yaml")
infra = resolve_infra(app_config)
infra.mcp_lifecycle.start()
```

### What `load_session()` does

`load_session(app_config, infra, session_id=...)` is the final step. It uses the already-started shared infrastructure to create a **fresh** `ResolvedConfig` for one session:

- fresh agents
- fresh orchestrations
- fresh entry point
- the same shared MCP lifecycle

This is the key distinction:

- `resolve_infra()` gives you **shared process-level infrastructure**
- `load_session()` gives you **session-level agent graph built on top of that infrastructure**

### Why this split matters for multi-tenant deployments

In a multi-tenant server, you usually do **not** want to re-parse YAML, re-resolve models, or restart MCP servers on every request. Those are process-level concerns.

Instead, you want:

- one validated config shared by the process
- one resolved infrastructure shared by the process
- one started MCP lifecycle shared by the process
- one fresh set of agents per tenant/session/request

Typical pattern:

```python
from strands_compose.config import load_config, load_session, resolve_infra

# Once at process startup
app_config = load_config("config.yaml")
infra = resolve_infra(app_config)
infra.mcp_lifecycle.start()

# Per request / websocket / tenant session
resolved = load_session(app_config, infra, session_id="tenant-123")
result = resolved.entry("Hello!")
```

This avoids paying the startup cost repeatedly while still keeping per-session agent state isolated.

### Session manager nuance

There is one especially important detail in `load_session()`:

- If you pass `session_id=...` **and** the config declares a global `session_manager`, strands-compose creates a **fresh session manager instance** for that session ID.
- If the config does **not** declare a global `session_manager`, `load_session()` does not invent one just because a `session_id` was provided.

So `session_id` is an override for configured session persistence — not a standalone feature by itself.

### Mental model

Use this rule of thumb:

- **`load()`** = convenience API for scripts and local apps
- **`load_config()`** = validate and freeze the declarative config
- **`resolve_infra()`** = build shared runtime dependencies, but do not start them yet
- **`load_session()`** = build one session's live agents/orchestrations from shared infra

If you're building a CLI, a notebook, or a one-shot script, use `load()`.

If you're building a long-running web server with many user sessions, use `load_config()` + `resolve_infra()` once, then `load_session()` for each session.

---

[Next: Chapter 18 — Full Reference →](Chapter_18.md)
