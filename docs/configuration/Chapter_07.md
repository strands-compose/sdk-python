# Chapter 7: Session Persistence — Memory That Survives Restarts

[← Back to Table of Contents](README.md) | [← Previous: Hooks](Chapter_06.md)

---

By default, agents are stateless — each `load()` call starts fresh. The `session_manager` section enables persistent conversation history.

## Global Session Manager

Define a session manager at the root level and **every agent** inherits it:

```yaml
session_manager:
  provider: file
  params:
    storage_dir: ./.sessions
    session_id: my-session-001

agents:
  assistant:
    model: default
    system_prompt: "You remember everything."

entry: assistant
```

## Built-in Providers

| Provider | Backend | Required Package |
|----------|---------|------------------|
| `file` | Local filesystem | *(included)* |
| `s3` | Amazon S3 bucket | *(included, needs AWS creds)* |
| `agentcore` | Bedrock AgentCore Memory | `pip install strands-compose[agentcore-memory]` |

### File Provider

```yaml
session_manager:
  provider: file
  params:
    storage_dir: ./.sessions
    session_id: my-session
```

Sessions are stored as files in `storage_dir`. Delete the directory to start fresh.

### S3 Provider

```yaml
session_manager:
  provider: s3
  params:
    bucket_name: my-agent-sessions
    session_id: prod-session-001
```

Requires AWS credentials in the environment.

### AgentCore Provider

The `agentcore` provider requires a unique `actor_id` per agent and **cannot** be set globally — set it per-agent instead:

```yaml
agents:
  assistant:
    model: default
    system_prompt: "You are helpful."
    session_manager:
      provider: agentcore
      params:
        actor_id: assistant
        memory_id: my-memory-store
```

## Per-Agent Session Manager

Any agent can override the global session manager with its own:

```yaml
session_manager:
  provider: file
  params:
    storage_dir: ./.sessions

agents:
  persistent_agent:
    model: default
    system_prompt: "I remember."
    # Inherits the global file session manager

  stateless_agent:
    model: default
    system_prompt: "I forget."
    session_manager: ~             # <-- Explicit opt-out with YAML null (~)
```

Setting `session_manager: ~` (YAML null) on an agent **explicitly opts it out** of the global default. This is important — without this, it would inherit the global one.

## Session ID Resolution

When no `session_id` is provided, strands-compose generates a random UUID — meaning each run gets a fresh session. The resolution order is:

1. **Runtime override** — via `load_session(..., session_id="abc")`
2. **`params.session_id`** — from YAML config
3. **Random UUID** — fresh session per run

## Custom Session Manager

For anything beyond the built-in providers, point `type` to your own class:

```yaml
session_manager:
  type: my_package.sessions:RedisSessionManager
  params:
    host: localhost
    port: 6379
```

The class must be a subclass of `strands.session.SessionManager`. When `type` is set, `provider` is ignored.

## Swarm Agents and Sessions

**Important limitation**: agents that participate in a Swarm orchestration **cannot** have a session manager. This is a strands-agents limitation. If a global session manager is set and an agent is used in a swarm, strands-compose will raise a clear error:

```
ConfigurationError: Agent 'drafter' is in swarm orchestration and cannot
have a session manager (source: global 'session_manager:' in config).
Fix: Add 'session_manager: ~' to agent 'drafter' to opt out of the global default.
```

The fix: add `session_manager: ~` to each swarm agent to opt out.

> **Tips & Tricks**
>
> - For development, `file` provider with a fixed `session_id` is great — restart your script and the agent remembers your conversation.
> - For server/API deployments, use `load_session()` with a per-request `session_id` to isolate conversations between users. See [the multi-tenant pattern](#the-multi-tenant-server-pattern) below.
> - Delete the `.sessions/` directory to "factory reset" your agent's memory.

## The Multi-Tenant Server Pattern

For web servers where each HTTP request needs its own session:

```python
from strands_compose import load_config, resolve_infra, load_session

# Once at startup
app_config = load_config("config.yaml")
infra = resolve_infra(app_config)
infra.mcp_lifecycle.start()

# Per request
def handle_request(user_session_id: str, message: str):
    resolved = load_session(app_config, infra, session_id=user_session_id)
    return resolved.entry(message)
```

MCP servers are shared across sessions (started once), but agents and their conversation state are created fresh per session.

---

[Next: Chapter 8 — Conversation Managers →](Chapter_08.md)
