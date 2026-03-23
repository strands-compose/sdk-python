# Chapter 18: Full Reference — Every Field at a Glance

[← Back to Table of Contents](README.md) | [← Previous: The Loading Pipeline](Chapter_17.md)

---

## Root Config

```yaml
version: "1"          # Optional, defaults to "1"
vars: {}              # Variable definitions (removed after interpolation)
models: {}            # Named model definitions
agents: {}            # Named agent definitions (required: at least one)
orchestrations: {}    # Named orchestration definitions
mcp_servers: {}       # Named MCP server definitions
mcp_clients: {}       # Named MCP client connections
session_manager: {}   # Global session manager
entry: "name"         # Required: entry point agent or orchestration
log_level: "WARNING"  # Optional: DEBUG, INFO, WARNING, ERROR
```

## ModelDef

```yaml
models:
  name:
    provider: bedrock | openai | ollama | gemini | module.path:CustomModel
    model_id: "model-identifier"
    params: {}        # Provider-specific kwargs
```

## AgentDef

```yaml
agents:
  name:
    type: null                     # Custom factory: module.path:factory_func
    agent_kwargs: {}               # Extra kwargs for Agent() or custom factory
    model: "model_name"            # String ref to models: or inline ModelDef
    system_prompt: "..."           # System prompt string
    description: "..."             # Agent description (used in orchestration tools)
    tools: []                      # List of tool spec strings
    hooks: []                      # List of HookDef objects or import path strings
    mcp: []                        # List of MCP client names
    tool_labels: {}                # Tool name -> display label mapping
    conversation_manager: null     # ConversationManagerDef
    session_manager: null          # Per-agent SessionManagerDef (overrides global)
```

## HookDef

```yaml
hooks:
  # Inline object form
  - type: module.path:ClassName    # or ./file.py:ClassName
    params: {}                     # Constructor kwargs

  # String shorthand (no params)
  - module.path:ClassName
```

## SessionManagerDef

```yaml
session_manager:
  provider: file | s3 | agentcore  # Built-in provider name
  type: null                        # Custom class: module.path:ClassName (overrides provider)
  params: {}                        # Constructor kwargs (session_id, storage_dir, etc.)
```

## ConversationManagerDef

```yaml
conversation_manager:
  type: strands.agent:SlidingWindowConversationManager
  params: {}                       # Constructor kwargs (window_size, etc.)
```

## MCPServerDef

```yaml
mcp_servers:
  name:
    type: ./server.py:create       # Factory function: module.path:func or ./file.py:func
    params: {}                     # Forwarded to factory (port, host, etc.)
```

## MCPClientDef

```yaml
mcp_clients:
  name:
    # Exactly one of:
    server: "server_name"          # Reference to mcp_servers entry
    url: "https://..."             # External MCP server URL
    command: ["cmd", "arg"]        # Stdio subprocess command

    transport: null                # Override: "streamable-http" | "sse" | "stdio"
    params: {}                     # Forwarded to strands MCPClient (prefix, startup_timeout, etc.)
    transport_options: {}          # Transport-specific options (headers, timeout, etc.)
```

## DelegateOrchestrationDef

```yaml
orchestrations:
  name:
    mode: delegate
    entry_name: "agent_name"       # Agent blueprint to fork
    connections:
      - agent: "target_name"      # Agent or orchestration name
        description: "..."         # Tool description for LLM
    session_manager: null          # Override session manager
    hooks: []                      # Additional hooks
    agent_kwargs: {}               # Override agent kwargs (merged)
```

## SwarmOrchestrationDef

```yaml
orchestrations:
  name:
    mode: swarm
    agents: [agent1, agent2]       # Participating agents
    entry_name: "agent1"           # Starting agent
    max_handoffs: 20               # Max handoffs
    max_iterations: 20             # Max iterations
    execution_timeout: 900.0       # Total timeout (seconds)
    node_timeout: 300.0            # Per-agent timeout (seconds)
    session_manager: null          # Swarm-level session manager
    hooks: []                      # Swarm-level hooks
```

## GraphOrchestrationDef

```yaml
orchestrations:
  name:
    mode: graph
    entry_name: "start_node"       # Node with no incoming edges
    edges:
      - from: "node_a"
        to: "node_b"
        condition: null            # Optional: ./file.py:func or module:func
    max_node_executions: null      # Safety cap for loops
    execution_timeout: null        # Total timeout (seconds)
    node_timeout: null             # Per-node timeout (seconds)
    reset_on_revisit: false        # Reset agent state on revisit
    session_manager: null          # Graph-level session manager
    hooks: []                      # Graph-level hooks
```

---

**Bonus**: [Quick Recipes →](Quick_Recipes.md)
