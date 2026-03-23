"""Raw pass-through StreamEvent converter."""

from __future__ import annotations

from typing import Any

from ..wire import StreamEvent
from .base import StreamConverter


class RawStreamConverter(StreamConverter):
    """Converts StreamEvents to raw JSON dicts (newline-delimited)."""

    def convert(self, event: StreamEvent) -> list[dict[str, Any]]:
        """Pass through as dict.

        Args:
            event: The StreamEvent to convert.

        Returns:
            A single-element list containing the event's dict representation.
        """
        return [event.asdict()]

    def done_marker(self) -> str:
        """No terminator needed for raw streams.

        Returns:
            An empty string.
        """
        return ""
