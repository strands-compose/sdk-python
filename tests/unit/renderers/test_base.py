"""Tests for the EventRenderer abstract base class."""

from __future__ import annotations

import pytest

from strands_compose.renderers.base import EventRenderer


class TestEventRendererABC:
    """EventRenderer cannot be instantiated directly."""

    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            EventRenderer()
