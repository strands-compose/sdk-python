"""ResolvedConfig — the result of resolving a config to live strands objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...manifest import build_manifest
from ...wire import make_event_queue

if TYPE_CHECKING:
    from strands import Agent

    from ...types import Node
    from ...wire import EventQueue


@dataclass(kw_only=True)
class ResolvedConfig:
    """Fully resolved config — agents ready to invoke.

    After calling :func:`~strands_compose.config.loaders.load`, use
    :meth:`wire_event_queue` to set up event streaming::

        resolved = load("config.yaml")
        event_queue = resolved.wire_event_queue()
    """

    agents: dict[str, Agent] = field(default_factory=dict)
    orchestrators: dict[str, Node] = field(default_factory=dict)
    entry: Node

    def wire_event_queue(
        self,
        *,
        session_id: str | None = None,
    ) -> EventQueue:
        """Wire every agent and orchestrator for event streaming.

        The returned queue already carries a SESSION_START event describing the
        session topology.

        .. warning::

            **Mutates** the agents and orchestrators on this instance by adding
            hooks and overwriting ``callback_handler``.  Call it only once.

        Args:
            session_id: Optional session ID to embed in events.

        Returns:
            A ready-to-use EventQueue.

        Raises:
            ValueError: If the entry node cannot be resolved by object identity.
        """
        manifest = build_manifest(self.agents, self.orchestrators, self.entry)
        event_queue = make_event_queue(
            self.agents,
            orchestrators=self.orchestrators,
            entry_name=manifest.entry.name,
            session_id=session_id,
        )
        event_queue.emit_session_start(manifest)
        return event_queue
