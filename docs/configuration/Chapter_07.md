# Chapter 7: Session Persistence — Memory That Survives Restarts

[← Back to Table of Contents](README.md) | [← Previous: Hooks](Chapter_06.md)

---

By default, agents are stateless — each `load()` call starts fresh. The `session_manager` section enables persistent conversation history.

## Global Session Manager

Define a session manager at the root level and **every agent** inherits it:

```yaml
session_manager:
  provider: file-snapshot
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
| `file-snapshot` (recommended) | Local folder, one snapshot per agent | *(included)* |
| `s3-snapshot` (recommended) | Amazon S3 bucket, one snapshot per agent | *(included, needs AWS creds)* |
| `file` | Local filesystem, one file per message | *(included)* |
| `s3` | Amazon S3 bucket, one object per message | *(included, needs AWS creds)* |
| `agentcore` | Bedrock AgentCore Memory | `pip install strands-compose[agentcore-memory]` |

### Snapshot Providers (recommended)

`file-snapshot` and `s3-snapshot` use strands' `SnapshotSessionManager`. Each agent's whole
state (messages, agent state, system prompt) is saved as one snapshot and restored on the next
`load()`. Use them for new configs:

- They work with `agent_kwargs.context_manager`. `file`, `s3` and `agentcore` cannot be
  combined with it on strands-agents 1.63+.
- A restore brings back the conversation as it was last saved, including summaries and
  trimmed tool results.
- They also work as the session manager of a Swarm or Graph orchestration.

```yaml
session_manager:
  provider: file-snapshot
  params:
    storage_dir: ./.sessions      # default: ./.strands, relative to the working directory
```

```yaml
session_manager:
  provider: s3-snapshot
  params:
    bucket: my-agent-sessions     # required
    prefix: prod/                 # optional
    region_name: eu-central-1     # optional
```

| Param | Provider | Required | Default | Accepted values / meaning |
|-------|----------|----------|---------|---------------------------|
| `bucket` | `s3-snapshot` | yes | none | Non-empty S3 bucket name. |
| `storage_dir` | `file-snapshot` | no | `./.strands/` | Non-empty folder path. `null` also means the default folder. |
| `prefix` | `s3-snapshot` | no | `""` | Key prefix inside the bucket. `null` also means no prefix. |
| `region_name` | `s3-snapshot` | no | AWS environment | AWS region name. |
| `session_id` | both | no | runtime id, then random UUID | As for every provider. |
| `save_latest_on` | both | no | `invocation` | `invocation`: save after each turn. `message`: also save after every message; this rewrites the whole snapshot each time. |
| `multi_agent_save_latest_on` | both | no | `node` | Swarm or Graph: `node` or `invocation`. |

Unknown params and invalid values are rejected when the config is loaded, so
`strands-compose check` catches them.

The same layout is used in the folder and in the bucket (after the prefix):

```
session/<session_id>/scopes/agent/<agent_name>/snapshots/snapshot_latest.json
session/<session_id>/scopes/multiAgent/<orchestration_name>/snapshots/snapshot_latest.json
context/<session_id>/scopes/agent/<agent_name>/...   # tool results a context manager set aside
```

The agent gets the same storage, so tool results a context manager sets aside are stored once,
next to the session.

> **Switching an existing deployment:** snapshot providers do not read sessions written by
> `file` or `s3`, and strands has no migration. Agents start fresh for old session ids. Keep
> the old provider while those sessions still matter.

> **Config changes after a save:** a snapshot includes the system prompt and agent state.
> Restoring an old session restores those saved values. Use a new session id when a changed
> prompt or initial state must take effect.

> **MinIO or LocalStack:** `s3-snapshot` has no `endpoint_url`. Set the `AWS_ENDPOINT_URL_S3`
> environment variable instead.

> **One writer per scope:** two processes writing the same session id and the same agent or
> orchestration id overwrite the same latest snapshot. The last save wins.

### File Provider

```yaml
session_manager:
  provider: file
  params:
    storage_dir: ./.sessions
    session_id: my-session
```

Sessions are stored as files in `storage_dir`. Delete the directory to start fresh.

Cannot be combined with `agent_kwargs.context_manager` (strands-agents 1.63+). Use `file-snapshot`.

### S3 Provider

```yaml
session_manager:
  provider: s3
  params:
    bucket: my-agent-sessions
    session_id: prod-session-001
```

Requires AWS credentials in the environment.

Cannot be combined with `agent_kwargs.context_manager` (strands-agents 1.63+). Use `s3-snapshot`.

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

1. **Runtime override** — via `load(..., session_id="abc")`
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

## Swarm and Graph Agents and Sessions

**Important limitation**: agents that participate in a Swarm or Graph orchestration **cannot** have a session manager. If a global session manager is set and an agent is used in a swarm or graph, strands-compose will raise a clear error:

```
ConfigurationError: Agent 'drafter' is in a swarm or graph orchestration and cannot have a session manager (source: global 'session_manager:' in config).
Strands does not yet support session persistence for Swarm or Graph node agents.
Fix: Add 'session_manager: ~' to agent 'drafter' to opt out of the global default.
```

The fix: add `session_manager: ~` to each swarm or graph node agent to opt out.

> **Tips & Tricks**
>
> - For development, `file-snapshot` provider with a fixed `session_id` is great — restart your script and the agent remembers your conversation.
> - For server/API deployments, use `load()` with a per-session `session_id`. strands-compose
>   computes a single `effective_session_id` from your value and threads it to every agent and
>   orchestration, so all agents in one request share the same session folder. See
>   [the multi-session pattern](#the-multi-session-server-pattern) below.
> - Delete the `.sessions/` directory to "factory reset" your agent's memory.

## The Multi-Session Server Pattern

For web servers where each request needs its own session:

```python
from strands_compose import load, load_config

# Once at startup — parse and validate, no live objects yet
app_config = load_config("config.yaml")

# Per session
def handle_session(user_session_id: str, message: str):
    resolved = load(app_config, session_id=user_session_id)
    return resolved.entry(message)
```

YAML is parsed once; every `load()` call builds its own agents, so sessions never share conversation state. Cache the `ResolvedConfig` for follow-up turns within the same session.

---

[Next: Chapter 8 — Conversation Managers →](Chapter_08.md)
