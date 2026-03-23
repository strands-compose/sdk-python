"""Tests for the StreamConverter ABC."""

from __future__ import annotations

from typing import Any

import pytest

from strands_compose.converters.base import StreamConverter
from strands_compose.converters.openai import OpenAIStreamConverter
from strands_compose.wire import StreamEvent


class _ConcreteConverter(StreamConverter):
    """Minimal concrete subclass to allow direct instantiation of the ABC."""

    def convert(self, event: StreamEvent) -> list[dict[str, Any]]:
        """Return empty list."""
        return []

    def done_marker(self) -> str:
        """Return empty string."""
        return ""


class TestStreamConverterABC:
    """StreamConverter ABC contract tests."""

    def test_cannot_instantiate_abstract_class_directly(self) -> None:
        """StreamConverter cannot be instantiated without implementing abstract methods."""
        with pytest.raises(TypeError):
            StreamConverter()

    def test_concrete_subclass_instantiates(self) -> None:
        """A fully concrete subclass can be instantiated."""
        conv = _ConcreteConverter()
        assert conv is not None

    def test_default_content_type_is_text_event_stream(self) -> None:
        """content_type() defaults to 'text/event-stream'."""
        conv = _ConcreteConverter()
        assert conv.content_type() == "text/event-stream"

    def test_openai_converter_is_instance_of_stream_converter(self) -> None:
        """OpenAIStreamConverter must be a StreamConverter subclass."""
        conv = OpenAIStreamConverter()
        assert isinstance(conv, StreamConverter)
