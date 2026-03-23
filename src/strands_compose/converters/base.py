"""Abstract base class for StreamEvent converters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..wire import StreamEvent


class StreamConverter(ABC):
    """Converts StreamEvent objects into protocol-specific output chunks.

    Each converter is stateful across one completion stream (tracks
    message id, created timestamp, tool call index, etc.). Create a
    new instance per request — do not share across concurrent requests.
    """

    @abstractmethod
    def convert(self, event: StreamEvent) -> list[dict[str, Any]]:
        """Convert one StreamEvent into zero or more output chunks.

        Returns a list (possibly empty) of serializable dicts.
        The transport layer is responsible for serializing and framing
        (e.g. 'data: {json}\\n\\n' for SSE). This method returns data
        shapes only — never pre-serialized strings.

        Args:
            event: The StreamEvent to convert.

        Returns:
            A list of serializable dicts representing output chunks.
        """
        ...

    @abstractmethod
    def done_marker(self) -> str:
        """Terminal sentinel to emit after the stream ends.

        E.g. 'data: [DONE]\\n\\n' for OpenAI SSE.
        Return empty string if the protocol needs no terminator.

        Returns:
            The terminal string to emit, or empty string if none.
        """
        ...

    def content_type(self) -> str:
        """MIME type for the HTTP streaming response.

        Returns:
            The MIME type string.
        """
        return "text/event-stream"
