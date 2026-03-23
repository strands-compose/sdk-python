# Quick Recipes

[← Back to Table of Contents](README.md) | [← Previous: Full Reference](Chapter_18.md)

---

Copy-paste-ready configs for common patterns.

## The Kitchen Sink

Everything in one config:

```yaml
vars:
  MODEL: ${MODEL:-us.anthropic.claude-sonnet-4-6-v1:0}
  TONE: ${TONE:-professional}

x-hooks: &safety_hooks
  - type: strands_compose.hooks:MaxToolCallsGuard
    params: { max_calls: 20 }
  - type: strands_compose.hooks:ToolNameSanitizer

models:
  default:
    provider: bedrock
    model_id: ${MODEL}

session_manager:
  provider: file
  params:
    storage_dir: ./.sessions
    session_id: ${SESSION_ID:-default}

agents:
  researcher:
    model: default
    hooks: *safety_hooks
    tools:
      - ./tools/research.py
    system_prompt: |
      You are a ${TONE} assistant.
      You specialize in research.
    session_manager: ~              # Opt out (used in swarm)

  reviewer:
    model: default
    hooks: *safety_hooks
    system_prompt: "You review content."
    session_manager: ~              # Opt out (used in swarm)

  qa_bot:
    model: default
    hooks: *safety_hooks
    system_prompt: "Run QA checks."

  coordinator:
    model: default
    hooks: *safety_hooks
    conversation_manager:
      type: strands.agent:SlidingWindowConversationManager
      params: { window_size: 40 }
    system_prompt: "Coordinate the team."

orchestrations:
  content_team:
    mode: swarm
    agents: [researcher, reviewer]
    entry_name: researcher
    max_handoffs: 10

  pipeline:
    mode: delegate
    entry_name: coordinator
    connections:
      - agent: content_team
        description: "Content production team."
      - agent: qa_bot
        description: "Quality assurance."

entry: pipeline
log_level: ${LOG_LEVEL:-WARNING}
```

## Minimal Single Agent

```yaml
agents:
  bot:
    system_prompt: "You answer questions."
entry: bot
```

## Two Models, One Agent

```yaml
models:
  fast:
    provider: bedrock
    model_id: us.anthropic.claude-sonnet-4-6-v1:0
  smart:
    provider: openai
    model_id: gpt-4o

agents:
  assistant:
    model: ${WHICH_MODEL:-fast}
    system_prompt: "You are helpful."
entry: assistant
```

---

[← Back to Table of Contents](README.md)
