# 05 — Hooks

> Attach middleware to every agent invocation — custom or built-in.

## What this shows

- How to write a **custom hook** (`FingerprintHook`) that counts tool calls and prints a summary at the end of each invocation
- How to wire it in `config.yaml` alongside built-in hooks — no Python glue code needed
- `MaxToolCallsGuard` — prevents Agent from infinite loop of tool calling. Sets max allowed calls per invocation.
- `ToolNameSanitizer` — some models inject extra tokens into tool names. This hook strips them so the agent can call tools correctly

## How it works

Hooks are Python classes that implement the strands `HookProvider` interface. No decorator — just a `register_hooks(self, registry)` method:

```python
class FingerprintHook(HookProvider):
    def __init__(self) -> None:
        self._tool_calls = 0

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(AfterToolCallEvent, self._on_after_tool)
        registry.add_callback(AfterInvocationEvent, self._on_after_invocation)

    def _on_after_tool(self, event: AfterToolCallEvent) -> None:
        self._tool_calls += 1

    def _on_after_invocation(self, event: AfterInvocationEvent) -> None:
        print(f">>> THIS IS YOUR CUSTOM HOOK: Agent used {self._tool_calls} tools <<<")
        self._tool_calls = 0  # reset for the next turn
```

In `config.yaml`, hooks are listed under the agent. They fire in order:

```yaml
hooks:
  - type: ./hooks.py:FingerprintHook           # custom — from local file
  - type: strands_compose.hooks:MaxToolCallsGuard
    params:
      max_calls: 5
  - type: strands_compose.hooks:ToolNameSanitizer
```

The spec format for hooks is always `module_or_file:ClassName` — the class name is required (no bulk scan).

## Good to know

- `BeforeToolCallEvent` and `AfterToolCallEvent` are the most common hook points. See strands docs for the full list.
- Multiple hooks on the same agent compose in declaration order. Each fires independently.
- `MaxToolCallsGuard` uses a two-phase approach: the first over-limit call cancels the tool and instructs the LLM to write a final answer (the loop continues so it gets one more turn). If the LLM ignores that and requests another tool, the event loop is hard-stopped. A `WARNING` is logged on both phases.
- `ToolNameSanitizer` is often necessary — some models append extra tokens to tool names (e.g. `search<|x|>` instead of `search`), causing strands to silently fail the tool lookup. The hook strips the artifacts before strands resolves the name.
- The tools in `custom_tools.py` are mock stubs that return deterministic fake data so the example works without external APIs.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/05_hooks/main.py
```

## Try these prompts

At the end you'll see our FingerprintHook log:
`>>> THIS IS YOUR CUSTOM HOOK: Agent used N tools <<<`

- `Research the impact of electric vehicles on city air quality. Be thorough.`
- `Find facts about Python programming and write a short summary.`
- `What do we know about climate change and renewable energy?`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
