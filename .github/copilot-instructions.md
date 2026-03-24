# strands-compose — Copilot Instructions

This is **strands-compose**: a declarative multi-agent orchestration library for [strands-agents](https://github.com/strands-agents/sdk-python).
It reads YAML configs and returns fully wired, plain `strands` objects — no wrappers, no subclasses.

---

## Architecture — NON-NEGOTIABLE

1. **Strands-first** — always check `.venv/lib/python*/site-packages/strands/` before implementing anything. If strands provides it, use it directly.
2. **Thin wrapper** — translate YAML → Python objects, then get out of the way.
3. **Composition over inheritance** — small, focused components that compose.
4. **Explicit over implicit** — no auto-registration, no global singletons.
5. **Single responsibility** — each module does one thing.
6. **Testable in isolation** — no global state, every unit testable without other components.

## Python Rules

- `from __future__ import annotations` at the top of every module.
- Every public function/method/class must be fully typed — parameters and return type.
- Use `X | None`, `X | Y`, `list`, `dict`, `tuple` — never `Optional`, `Union`, `List`, `Dict`.
- Google-style docstrings on every public class, function, and method.
- Class docstring goes on `__init__`, not the class body.
- Early returns always — handle edge cases first, max 3 nesting levels.
- Raise specific exceptions (`ValueError`, `KeyError`, `TypeError`, `RuntimeError`) with context.
- Never silently swallow exceptions. No bare `except:`.
- Return copies from properties: `return list(self._items)`.
- `logging.getLogger(__name__)` — never `print()` for diagnostics.
- No `eval()`, `exec()`, `pickle` for untrusted data, `subprocess(shell=True)`.
- No hardcoded secrets — use env vars.
- Import order: stdlib → third-party → local (ruff-enforced).
- `__all__` only in `__init__.py`.

## Naming

- Classes: `PascalCase` | functions/methods: `snake_case` | constants: `UPPER_SNAKE_CASE` | private: `_prefix`
- No abbreviations in public API. Boolean params: `is_`, `has_`, `enable_` prefixes.

## Key Strands APIs (do NOT reimplement)

| What | Import path |
|------|-------------|
| `Agent` | `strands.agent.agent` |
| Hook events | `strands.hooks.events` — `BeforeInvocationEvent`, `AfterInvocationEvent`, `BeforeModelCallEvent`, `AfterModelCallEvent`, `BeforeToolCallEvent`, `AfterToolCallEvent` |
| `HookProvider` | `strands.hooks` — implement `register_hooks(registry)` |
| `MCPClient` | `strands.tools.mcp.mcp_client` |
| `SessionManager` | `strands.session` — `FileSessionManager`, `S3SessionManager` |
| Multi-agent | `strands.multiagent` — `Swarm`, `Graph` |
| `ToolRegistry` | `strands.tools.registry` |
| `@tool` decorator | `strands.tools.decorator` |

## Testing

- Every public function gets at least one test. Test behavior, not implementation.
- Use pytest fixtures, `parametrize`, `tmp_path`. Mock external dependencies.
- Name tests descriptively: `test_interpolate_missing_var_without_default_raises_value_error`.

## Tooling

```bash
uv run just install      # install deps + git hooks (once after clone)
uv run just check        # lint + type check + security scan
uv run just test         # pytest with coverage (≥70%)
uv run just format       # auto-format with ruff
```

## Directory Structure

```
src/strands_compose/
├── __init__.py              # Public API — load(), ResolvedConfig
├── models.py                # Pydantic config models (AgentConfig, ModelConfig, …)
├── types.py                 # Shared type aliases
├── utils.py                 # Miscellaneous helpers
├── exceptions.py            # Custom exception hierarchy
├── wire.py                  # Final assembly — wires all resolved objects into ResolvedConfig
├── config/                  # YAML loading, validation, interpolation
│   ├── schema.py            # JSON-schema for config validation
│   ├── interpolation.py     # ${VAR:-default} interpolation
│   ├── loaders/             # File/string/dict loaders, helpers, validators
│   └── resolvers/           # Per-key resolvers (agents, models, mcp, hooks, …)
│       └── orchestrations/  # Orchestration builder and planner
│           ├── builders.py  # Build delegate, swarm, graph objects
│           └── planner.py   # Resolve orchestration config to plan
├── converters/              # Config dict → strands objects
│   ├── base.py              # BaseConverter protocol
│   ├── openai.py            # OpenAI-specific conversion
│   └── raw.py               # Raw/passthrough conversion
├── hooks/                   # Built-in HookProvider implementations
│   ├── event_publisher.py   # Streaming event queue publisher
│   ├── max_calls_guard.py   # Max tool-call circuit breaker
│   ├── stop_guard.py        # Agent stop-signal hook
│   └── tool_name_sanitizer.py  # Sanitize tool names for model compatibility
├── mcp/                     # MCP server/client lifecycle
│   ├── client.py            # MCPClient factory and wiring
│   ├── lifecycle.py         # Server startup, readiness polling, shutdown
│   ├── server.py            # Local Python server launcher
│   └── transports.py        # Transport builders (stdio, streamable_http)
├── renderers/               # Terminal output rendering
│   ├── base.py              # BaseRenderer protocol
│   └── ansi.py              # ANSI colour renderer
├── startup/                 # Post-load validation and reporting
│   ├── validator.py         # Config correctness checks
│   └── report.py            # Human-readable startup report
└── tools/                   # Tool loading helpers
    ├── extractors.py        # Extract @tool functions from modules
    ├── loaders.py           # Import modules by path/name
    └── wrappers.py          # Wrap callables as strands tools

tests/
├── unit/                    # Unit tests (mirrors src/ structure)
│   ├── config/              # Tests for config loading, schema, interpolation, resolvers
│   ├── converters/          # Tests for converter modules
│   ├── hooks/               # Tests for hook providers
│   ├── mcp/                 # Tests for MCP lifecycle
│   ├── models/              # Tests for Pydantic config models
│   ├── renderers/           # Tests for renderers
│   └── startup/             # Tests for validator and report
├── integration/             # Integration tests (real strands objects)
└── examples/                # Smoke tests for all examples/
```

## Logging Style

Use `%s` interpolation with structured field-value pairs — never f-strings:

```python
# Good
logger.debug("agent_id=<%s>, tool=<%s> | tool call started", agent_id, tool_name)
logger.warning("path=<%s>, reason=<%s> | config file not found", path, reason)

# Bad
logger.debug(f"Tool {tool_name} called on agent {agent_id}")  # no f-strings
logger.info("Config loaded.")                                  # no punctuation
```

- Field-value pairs first: `key=<value>` separated by commas
- Human-readable message after ` | `
- `<>` around values (makes empty values visible)
- Lowercase messages, no trailing punctuation
- `%s` format strings, not f-strings (lazy evaluation)

## Things to Do

- Check `.venv/lib/python*/site-packages/strands/` before implementing — use strands if it exists
- `from __future__ import annotations` at the top of every module
- Fully type every function signature (parameters + return type)
- Google-style docstring on every public class, function, and method
- Put class docstrings on `__init__`, not the class body
- Early returns — handle edge cases first, max 3 nesting levels
- Raise specific exceptions (`ValueError`, `KeyError`, `TypeError`, `RuntimeError`) with context
- Return copies from properties exposing mutable state: `return list(self._items)`
- Use structured logging with `%s` and field-value pairs
- Run `uv run just check` then `uv run just test` before committing

## Things NOT to Do

- Don't reimplement what strands already provides — check first
- Don't use `Optional[X]`, `Union[X, Y]`, `List`, `Dict` — use `X | None`, `list`, `dict`
- Don't use `print()` for diagnostics — use `logging.getLogger(__name__)`
- Don't use f-strings in log calls — use `%s` interpolation
- Don't swallow exceptions silently — no bare `except:`
- Don't add `__all__` outside `__init__.py`
- Don't hardcode secrets — use env vars
- Don't use `eval()`, `exec()`, `pickle` for untrusted data, or `subprocess(shell=True)`
- Don't commit without running `uv run just check`
- Don't add comments about what changed or temporal context ("recently refactored", "moved from")

## Agent-Specific Notes

- Make the **smallest reasonable change** to achieve the goal — don't refactor unrelated code
- Prefer simple, readable, maintainable solutions over clever ones
- When unsure where something belongs, check the Directory Structure above
- Comments should explain **what** and **why**, never **when** or **how it changed**
- If you find something broken while working, fix it — don't leave it commented out
- Never add or change files outside the scope of the task
