"""Custom hooks for the 05_hooks example.

Shows how to write your own HookProvider subclass.
Hooks are class-based — no decorator needed, just implement register_hooks().
"""

from __future__ import annotations

from typing import Any

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import AfterInvocationEvent, AfterToolCallEvent


class FingerprintHook(HookProvider):
    """Counts tool calls and prints a summary at the end of each invocation.

    Drop-in example of a custom hook — use this as a template for logging,
    metrics, or any side-effect you want to attach to the agent lifecycle.
    """

    def __init__(self) -> None:
        self._tool_calls: int = 0

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Wire callbacks to the events we care about."""
        registry.add_callback(AfterToolCallEvent, self._on_after_tool)
        registry.add_callback(AfterInvocationEvent, self._on_after_invocation)

    def _on_after_tool(self, event: AfterToolCallEvent) -> None:
        self._tool_calls += 1

    def _on_after_invocation(self, event: AfterInvocationEvent) -> None:
        msg = f"Agent '{event.agent.name}' used {self._tool_calls} tools in this turn."
        print(f"\n\n\033[32m>>> CUSTOM HOOK: {msg} <<<\033[0m\n")
        self._tool_calls = 0  # reset for the next turn
