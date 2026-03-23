"""External stop-signal hooks.

Allows external code to signal an agent or multi-agent orchestration to
stop processing.  :class:`StopGuard` checks at every tool-call boundary;
:class:`MultiAgentStopGuard` checks at every node-call boundary.
"""

from __future__ import annotations

import sys
import threading
from typing import TYPE_CHECKING, Any

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import BeforeNodeCallEvent, BeforeToolCallEvent

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Callable


class StopGuard(HookProvider):
    """Cancels the agent's event loop when an external stop condition is met."""

    def __init__(self, stop_check: Callable[[], bool]) -> None:
        """Initialize the StopGuard.

        The stop condition is checked before every tool call.  When it returns
        ``True``, the current tool is cancelled and the event loop is stopped.

        Args:
            stop_check: Callable that returns ``True`` when the agent should stop.
                Must be thread-safe.  Common patterns:

                - ``threading.Event().is_set``
                - ``lambda: some_shared_flag``
                - ``lambda: not process_is_alive()``
        """
        self._should_stop = stop_check

    @override
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register the before-tool-call guard."""
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool)

    def _on_before_tool(self, event: BeforeToolCallEvent) -> None:
        """Cancel the tool and stop the event loop if the stop condition is met."""
        if not self._should_stop():
            return

        event.cancel_tool = "Agent stopped by external signal"
        event.invocation_state.setdefault("request_state", {})["stop_event_loop"] = True


def stop_guard_from_event(
    event: threading.Event | None = None,
) -> tuple[StopGuard, threading.Event]:
    """Create a StopGuard backed by a ``threading.Event``.

    Convenience factory for the common pattern of using a
    ``threading.Event`` as the external stop signal.  Can be used to
    wire stop-on-disconnect or for programmatic stop control.

    Example::

        guard, stop = stop_guard_from_event()
        agent.hooks.add_hook(guard)

        # later, from any thread:
        stop.set()  # agent stops at next tool-call boundary

    Args:
        event: Optional pre-existing ``threading.Event``.  When omitted a
            new event is created internally.

    Returns:
        Tuple of ``(guard, event)``.  Call ``event.set()`` to trigger the stop.
    """
    if event is None:
        event = threading.Event()
    return StopGuard(stop_check=event.is_set), event


class MultiAgentStopGuard(HookProvider):
    """Cancels node execution when an external stop condition is met."""

    def __init__(self, stop_check: Callable[[], bool]) -> None:
        """Initialize the MultiAgentStopGuard.

        Counterpart to :class:`StopGuard` for multi-agent orchestrations.
        Registers a ``BeforeNodeCallEvent`` callback on a Swarm or Graph's
        hook registry.  When the *stop_check* callable returns ``True``, the
        hook sets ``cancel_node`` to prevent the next node from starting.

        Args:
            stop_check: Callable returning ``True`` when stop is requested.
                Must be thread-safe.
        """
        self._stop_check = stop_check

    @override
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register the before-node-call guard."""
        registry.add_callback(BeforeNodeCallEvent, self._on_before_node)

    def _on_before_node(self, event: BeforeNodeCallEvent) -> None:
        """Cancel the node if the stop condition is met."""
        if self._stop_check():
            event.cancel_node = "stop requested"
