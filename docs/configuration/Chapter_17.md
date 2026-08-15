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
- Orchestration agent references → must exist in `agents` or `orchestrations`

## Step 8: Resolve Models and MCP Clients

Model objects and MCP client objects are created. MCP clients are not connected yet — strands connects one when it is attached to an agent.

## Step 9: Create Agents

Each agent definition is resolved: model looked up, tools loaded, hooks instantiated, MCP clients attached, session manager wired. Each agent is a fresh `strands.Agent` instance.

## Step 10: Wire Orchestrations

Orchestrations are topologically sorted and built in dependency order. Inner orchestrations first, outer orchestrations reference the already-built inner ones.

## Step 11: Return ResolvedConfig

The final `ResolvedConfig` has:
- `agents` — dict of all agents by name
- `orchestrators` — dict of all built orchestrations by name
- `entry` — the entry point (Agent, Swarm, or Graph)

## Sessions: one `load()` call per session

`load()` is the only entry point. Every call builds **fresh** agents, so every
call is an isolated session:

```python
from strands_compose import load

resolved = load("config.yaml")
result = resolved.entry("Hello!")
```

Agents hold conversation history, so they cannot be shared between sessions.
Everything else — models, MCP clients, tools, hooks — is built alongside them.

### Parse once, resolve per session

A long-running server should not re-read YAML on every request. Parse once with
`load_config()`, then hand the validated `AppConfig` to `load()` per session:

```python
from strands_compose import load, load_config

# Once at startup — fail fast on bad YAML
app_config = load_config("config.yaml")

# Per session
resolved = load(app_config, session_id="abc")
result = resolved.entry("Hello!")
```

`load_config()` returns pure data: no `Agent` instances, no MCP clients, nothing
started. That makes it safe to run in CI (`strands-compose check`) and cheap to
keep around for the life of the process.

### Two scopes, that's all

| Scope | Lasts | Holds |
|-------|-------|-------|
| **config** | as long as you keep it | validated `AppConfig` — pure data |
| **session** | one `load()` result | models, MCP clients, agents, orchestrations, session managers |

Follow-up turns reuse the same `ResolvedConfig` — that is what carries
conversation history forward. Call `load()` again only when you want a new
session.

### Releasing a session

There is normally nothing to tear down: strands stops an MCP client once every
agent holding it is gone. In a script that is process exit. In a long-running
process that discards sessions it is garbage collection, which is not immediate
if an agent sits in a reference cycle — so release those sessions explicitly:

```python
from strands import Agent

for node in (*resolved.agents.values(), *resolved.orchestrators.values()):
    if isinstance(node, Agent):
        node.cleanup()
```

Include the orchestrators. A `delegate` orchestration is an `Agent` forked from
its entry agent's blueprint and holds the same MCP clients, but it lives only in
`orchestrators` — a loop over `agents` alone would leave the client with a live
consumer and it would never stop. `Swarm` and `Graph` need no separate handling:
their nodes are the very same agent objects that are already in `agents`.

### Session ID resolution

`load()` computes a single effective session ID and threads it down to every
agent and orchestration leaf:

1. If you pass `session_id="my-id"`, that value is used as-is.
2. If you do **not** pass one but the config declares a global `session_manager:`,
   strands-compose looks for a `session_id` in `session_manager.params`. If found,
   that value is used; otherwise a fresh `uuid.uuid4()` is generated once and
   shared by all agents in that call — matching the "one folder per CLI run"
   behaviour.
3. If neither a `session_id` is provided nor a global `session_manager:` is
   configured, each agent or orchestration that declares its own
   `session_manager:` still gets one, generating its own ID.

When a global `session_manager:` is configured, this means every leaf that falls
back to it shares one ID — so one `load()` call produces one session folder, not
one per agent. Per-leaf `session_manager:` blocks with their own `session_id` or
`storage_dir` are independent of that.

---

[Next: Chapter 18 — Full Reference →](Chapter_18.md)
