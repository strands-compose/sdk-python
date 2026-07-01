"""Event queue wiring for streaming agent activities.

:class:`~strands_compose.types.StreamEvent` is the core event produced by
:class:`~strands_compose.hooks.EventPublisher` for all agent activity.

:class:`EventQueue` is a thin async queue wrapper that hides the sentinel
pattern from callers and brackets every invocation with a SESSION_START
event (carrying the session manifest) and a SESSION_END event.

:func:`make_event_queue` attaches :class:`~strands_compose.hooks.EventPublisher`
hooks to every agent so all per-agent events (TOKEN, REASONING, TOOL_START,
TOOL_END, INTERRUPT, AGENT_COMPLETE, and — for Swarm/Graph — NODE_START, NODE_STOP,
HANDOFF, MULTIAGENT_COMPLETE) flow into the shared queue.

Hooks are wired **once per session**.  Between requests on the same session,
call :meth:`EventQueue.flush` to discard stale events and reset the
SESSION_START / SESSION_END guards.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from strands import Agent
from strands.multiagent import Swarm
from strands.multiagent.graph import Graph

from .hooks import EventPublisher
from .types import EventType, SessionManifest, StreamEvent

if TYPE_CHECKING:
    from .types import Node


logger = logging.getLogger(__name__)


# ── Event Queue ──────────────────────────────────────────────────────────────

# Private sentinel — never exposed outside this module.
_SENTINEL = object()


class EventQueue:
    """Async event queue with hidden end-of-stream sentinel and session lifecycle."""

    def __init__(
        self,
        queue: asyncio.Queue,
        *,
        entry_name: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Initialize the EventQueue.

        Callers consume events via :meth:`get` (which returns ``None`` when the
        stream is closed) and signal completion via :meth:`close`.  The sentinel
        is an implementation detail — user code never sees or owns it.

        *entry_name* and *session_id* parameterise the SESSION_START and
        SESSION_END events emitted by :meth:`emit_session_start` and
        :meth:`close` respectively.

        Args:
            queue: The underlying asyncio.Queue to wrap.
            entry_name: The configured name of the entry node.  Used as
                ``agent_name`` on SESSION_START and SESSION_END events.
                Defaults to an empty string when not provided.
            session_id: The effective session id.  Included in the
                SESSION_END event payload as ``data["session_id"]``.
        """
        self._queue = queue
        self._entry_name = entry_name or ""
        self._session_id = session_id
        self._session_start_emitted = False
        self._session_end_emitted = False

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
        """Discard all currently queued events and reset lifecycle guards.

        Call this at the start of each request to clear any stale events left
        over from a previous invocation.  Resets the SESSION_START and
        SESSION_END guards so the next invocation cycle can re-emit them.
        """
        while not self._queue.empty():
            self._queue.get_nowait()
        self._session_start_emitted = False
        self._session_end_emitted = False

    def emit_session_start(self, manifest: SessionManifest) -> None:
        """Emit a SESSION_START event with the session manifest.

        Places a :class:`StreamEvent` with ``type=EventType.SESSION_START`` on
        the queue.  A guard prevents double-emission within the same
        invocation cycle (reset by :meth:`flush`).

        Args:
            manifest: The :class:`SessionManifest` describing the wired
                session.  Placed in the event payload as
                ``{"session_id": <session_id>, "manifest": manifest.model_dump()}``.
        """
        if self._session_start_emitted:
            return
        self._session_start_emitted = True
        self._put(
            StreamEvent(
                type=EventType.SESSION_START,
                agent_name=self._entry_name,
                data={
                    "session_id": self._session_id,
                    "manifest": manifest.model_dump(),
                },
            )
        )
        logger.debug("entry=<%s> | session_start emitted", self._entry_name)

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

    async def close(self, data: dict[str, Any] | None = None) -> None:
        """Signal end-of-stream.

        Emits a SESSION_END event before placing the sentinel on the queue.
        A guard prevents double-emission within the same invocation cycle
        (reset by :meth:`flush`).  Subsequent ``close()`` calls are no-ops
        for the SESSION_END emission but still place the sentinel — the
        method remains idempotent.

        Typically called in a ``finally`` block after the agent invocation
        finishes.

        Args:
            data: Additional data to include in the SESSION_END event.

        """
        if not self._session_end_emitted:
            self._session_end_emitted = True
            self._put(
                StreamEvent(
                    type=EventType.SESSION_END,
                    agent_name=self._entry_name,
                    data={"session_id": self._session_id, **(data or {})},
                )
            )
            logger.debug(
                "entry=<%s>, session_id=<%s> | session_end emitted",
                self._entry_name,
                self._session_id,
            )
        await self._queue.put(_SENTINEL)


# ── Wiring ───────────────────────────────────────────────────────────────────


def make_event_queue(
    agents: dict[str, Agent],
    *,
    orchestrators: dict[str, Node] | None = None,
    tool_labels: dict[str, str] | None = None,
    entry_name: str | None = None,
    session_id: str | None = None,
) -> EventQueue:
    """Attach :class:`~strands_compose.hooks.EventPublisher` hooks to agents.

    Every agent in *agents* receives an :class:`.EventPublisher` hook and a
    matching ``callback_handler`` so all per-agent event types flow into the
    returned :class:`EventQueue`.  Orchestrators (Swarm / Graph / delegate
    Agent) in *orchestrators* also get a publisher for NODE_START, NODE_STOP,
    HANDOFF, and MULTIAGENT_COMPLETE events.

    This function does **not** emit SESSION_START.  Callers that own a
    :class:`~strands_compose.types.SessionManifest` should call
    :meth:`EventQueue.emit_session_start` themselves; the common
    :class:`ResolvedConfig` workflow does this for you via
    :meth:`ResolvedConfig.wire_event_queue`.

    .. warning::

        This function **mutates** the passed-in agents and orchestrators by
        adding hooks and overwriting ``callback_handler``.  Call it only once
        per set of agents.

    Args:
        agents: Agents to wire, keyed by name.
        orchestrators: Built orchestrations keyed by name.
        tool_labels: Tool name → display label mapping forwarded to each
            :class:`.EventPublisher`.  Defaults to
            ``{name: "Delegating work to agent: <Name>"}`` for every agent.
        entry_name: The configured name of the entry node.  Stored on the
            EventQueue and used as ``agent_name`` on SESSION_START /
            SESSION_END events.
        session_id: The effective session id.  Stored on the EventQueue and
            included in the SESSION_END event payload.

    Returns:
        A ready-to-use :class:`EventQueue`.
    """
    event_queue = EventQueue(
        asyncio.Queue(maxsize=10000),
        entry_name=entry_name,
        session_id=session_id,
    )

    labels = {
        **{name: f"Delegating work to agent: {name.title()}" for name in agents},
        **(tool_labels or {}),
    }

    for name, agent in agents.items():
        pub = EventPublisher(callback=event_queue._put, agent_name=name, tool_labels=labels)
        agent.hooks.add_hook(pub)
        agent.callback_handler = pub.as_callback_handler()
        logger.debug("agent=<%s> | wired EventPublisher", name)

    for orch_name, orch in (orchestrators or {}).items():
        if not isinstance(orch, (Swarm, Graph, Agent)):
            continue
        orch_pub = EventPublisher(
            callback=event_queue._put,
            agent_name=orch_name,
            tool_labels=labels,
        )
        orch.hooks.add_hook(orch_pub)
        if isinstance(orch, Agent):
            orch.callback_handler = orch_pub.as_callback_handler()
        logger.debug("orchestrator=<%s> | wired EventPublisher", orch_name)

    return event_queue
