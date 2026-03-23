# 04 — Persistent Memory (Session Manager)

> Agents remember previous turns — conversations survive across restarts.

## What this shows

- `session_manager:` in YAML — persist conversation history to disk automatically
- Multi-turn memory: the agent recalls what you told it earlier in the same session
- Cross-restart memory: stop the process, start it again — the agent still knows you

## How it works

Add a `session_manager` block to your config. With `provider: file`, strands-compose saves
every turn to `.sessions/` on disk and restores it on the next `load()`.

```yaml
session_manager:
  provider: file
  params:
    storage_dir: ./.sessions
    session_id: example-04
```

That's it — no code changes needed. `load()` sees the session manager config, wires it into
the agent, and handles save/restore transparently.

### Global vs inline session manager

A **global** `session_manager` (top-level in config) is automatically assigned to **every
agent** that doesn't override it:

```yaml
# Global — all agents get this by default
session_manager:
  provider: file
  params:
    storage_dir: ./.sessions

agents:
  assistant:
    model: default
    system_prompt: You are helpful.
    # ← gets the global file session manager automatically

  analyst:
    model: default
    system_prompt: You analyze data.
    # ← also gets the global file session manager

  stateless_worker:
    model: default
    system_prompt: You do quick one-off tasks.
    session_manager: ~                         # ← explicitly opt out (null)
```

An **inline** `session_manager` on a specific agent overrides the global one:

```yaml
session_manager:
  provider: file
  params:
    storage_dir: ./.sessions

agents:
  assistant:
    model: default
    system_prompt: You are helpful.
    # ← inherits global (file)

  special_agent:
    model: default
    system_prompt: You have your own memory.
    session_manager:                            # ← inline override
      provider: file
      params:
        storage_dir: ./.special_sessions
```

The resolution order in code is:
1. **Agent has inline `session_manager:`** -> use it (takes priority)
2. **Agent has `session_manager: ~`** -> opt out, no session manager
3. **Otherwise** -> inherit the global `session_manager` (or `None` if there's no global)

## Good to know

**This example pins `session_id: example-04`**, so conversations persist across restarts
automatically. If you remove `session_id`, each `load()` generates a random UUID and you
get a fresh session every time.

```yaml
# Pinned — same session across restarts
session_id: example-04

# Omitted — random UUID, fresh session each run
# session_id:
```

**Delete `.sessions/` to start fresh.** The folder is created next to wherever you run the
command from.

**Without `session_manager`, every call starts blank.** There is no implicit memory — you
opt in explicitly through config.

**Swarm agents can't have a session manager.** If an agent is used inside a Swarm
orchestration, strands doesn't support session persistence for it. Use `session_manager: ~`
to opt that agent out of the global default, or you'll get an error at load time.

> [!WARNING]
> **Swarm + session manager is not yet supported.**
> Strands Agents does not currently allow session persistence for agents inside a Swarm
> orchestration. If you have a global `session_manager:`, any agent used in a Swarm must
> explicitly opt out with `session_manager: ~`. This restriction may be lifted in a future
> version of strands-agents.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/04_session/main.py
```

## Try these prompts

Run the example and type in order:

1. `My name is Alice and I work as a data engineer.`
2. `What do you know about me so far?`
3. Exit and run again — the agent should still remember your name.

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
