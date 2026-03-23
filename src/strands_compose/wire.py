"""Event queue wiring for streaming agent activities.

:class:`~strands_compose.types.StreamEvent` is the core event produced by
:class:`~strands_compose.hooks.EventPublisher` for all agent activity.

:class:`EventQueue` is a thin async queue wrapper that hides the sentinel
pattern from callers.  :func:`make_event_queue` attaches
:class:`~strands_compose.hooks.EventPublisher` hooks to every agent
so all events (TOKEN, REASONING, TOOL_START, TOOL_END, COMPLETE,
and — for Swarm/Graph — NODE_START, NODE_STOP, HANDOFF, MULTIAGENT_COMPLETE)
flow into the shared queue.

Hooks are wired **once per session**. Between requests on the same session,
call :meth:`EventQueue.flush` to discard stale events.

Key Features:
    - Async queue with hidden end-of-stream sentinel pattern
    - Thread-safe event injection for cross-thread publishing
    - Automatic EventPublisher wiring for agents and orchestrators
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from strands import Agent
from strands.multiagent import Swarm
from strands.multiagent.graph import Graph

from .hooks import EventPublisher
from .types import StreamEvent

if TYPE_CHECKING:
    from .types import Node


logger = logging.getLogger(__name__)


# ── Event Queue ──────────────────────────────────────────────────────────────

# Private sentinel — never exposed outside this module.
_SENTINEL = object()


class EventQueue:
    """Async event queue with a hidden end-of-stream sentinel."""

    def __init__(self, queue: asyncio.Queue) -> None:
        """Initialize the EventQueue.

        Callers consume events via :meth:`get` (which returns ``None`` when the
        stream is closed) and signal completion via :meth:`close`.  The sentinel
        is an implementation detail — user code never sees or owns it.

        Example::

            events = make_event_queue(config.agents)


            async def _run():
                try:
                    await config.entry.invoke_async(prompt)
                finally:
                    await events.close()


            asyncio.create_task(_run())
            while (event := await events.get()) is not None:
                yield event.asdict()

        Args:
            queue: The underlying asyncio.Queue to wrap.
        """
        self._queue = queue

    # -- Internal ----------------------------------------------------------

    def _put(self, event: StreamEvent | object) -> None:
        """Place an item on the queue (non-blocking).

        Used as the :class:`~strands_compose.hooks.EventPublisher` callback.
        Drops the event with a warning when the queue is full.
        """
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            if event is not _SENTINEL:
                logger.warning(
                    "maxsize=<%d> | event queue full, dropping event", self._queue.maxsize
                )

    # -- Public API --------------------------------------------------------

    def flush(self) -> None:
        """Discard all currently queued events.

        Call this at the start of each request to clear any stale events
        left over from a previous invocation.
        """
        while not self._queue.empty():
            self._queue.get_nowait()

    async def get(self) -> StreamEvent | None:
        """Wait for the next event.

        Returns:
            The next :class:`StreamEvent`, or ``None`` when the stream
            has been closed via :meth:`close`.
        """
        item = await self._queue.get()
        return None if item is _SENTINEL else item

    def put_event(self, event: StreamEvent) -> None:
        """Place an event on the queue (non-blocking, thread-safe).

        Useful for injecting out-of-band events such as error signals.
        """
        self._put(event)

    async def close(self) -> None:
        """Signal end-of-stream.

        Places the sentinel on the queue so that the consumer loop
        terminates cleanly.  Typically called in a ``finally`` block after
        the agent invocation finishes.
        """
        await self._queue.put(_SENTINEL)


def make_event_queue(
    agents: dict[str, Agent],
    *,
    orchestrators: dict[str, Node] | None = None,
    tool_labels: dict[str, str] | None = None,
) -> EventQueue:
    """Attach :class:`~strands_compose.hooks.EventPublisher` hooks to agents.

    Every agent in *agents* receives an :class:`.EventPublisher` hook and a
    matching ``callback_handler`` so that all event types flow into the
    returned :class:`EventQueue`.

    Orchestrators (Swarm / Graph) in *orchestrators* also get a publisher
    for NODE_START, NODE_STOP, HANDOFF, and MULTIAGENT_COMPLETE events.

    .. warning::

        This function **mutates** the passed-in agents and orchestrators
        by adding hooks and overwriting ``callback_handler``.  Call it
        only once per set of agents.  For the common ``ResolvedConfig``
        workflow, prefer :meth:`ResolvedConfig.wire_event_queue` which
        makes the mutation explicit.

    Args:
        agents: Agents to wire, keyed by name.
        orchestrators: Built orchestrations keyed by name.
        tool_labels: Tool name -> display label mapping forwarded to each
            :class:`.EventPublisher`.  Defaults to
            ``{name: "Delegating work to agent: <Name>"}`` for every agent.

    Returns:
        A ready-to-use :class:`EventQueue`.
    """
    event_queue = EventQueue(asyncio.Queue(maxsize=10000))

    labels = {
        **{name: f"Delegating work to agent: {name.title()}" for name in agents},
        **(tool_labels or {}),
    }

    # Wire every agent with a publisher.
    for name, agent in agents.items():
        pub = EventPublisher(callback=event_queue._put, agent_name=name, tool_labels=labels)
        agent.hooks.add_hook(pub)
        agent.callback_handler = pub.as_callback_handler()
        logger.debug("agent=<%s> | wired EventPublisher", name)

    # Wire orchestrators (Swarm / Graph instances).
    for orch_name, orch in (orchestrators or {}).items():
        if isinstance(orch, (Swarm, Graph, Agent)):
            orch_pub = EventPublisher(
                callback=event_queue._put,
                agent_name=orch_name,
                tool_labels=labels,
            )
            orch.hooks.add_hook(orch_pub)

            # If orch is an Agent, it needs the callback_handler set like any other agent.
            if isinstance(orch, Agent):
                orch.callback_handler = orch_pub.as_callback_handler()

            logger.debug("orchestrator=<%s> | wired EventPublisher", orch_name)

    return event_queue
