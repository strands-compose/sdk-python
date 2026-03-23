"""Abstract base class for event renderers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..wire import StreamEvent


class EventRenderer(ABC):
    """Renders :class:`StreamEvent` objects to a terminal.

    Subclasses implement :meth:`render` to handle one event at a time.
    The renderer is **stateful** — it tracks inline token streaming so
    structured events can break the line cleanly.

    Create a new instance per prompt / conversation turn.
    """

    @abstractmethod
    def render(self, event: StreamEvent) -> None:
        """Render a single event to the terminal.

        Args:
            event: The event to render.
        """
        ...

    @abstractmethod
    def flush(self) -> None:
        """Flush any pending output.

        Call after the event stream ends to ensure a trailing token
        stream is newline-terminated.
        """
        ...
