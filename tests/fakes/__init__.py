"""Hand-written fakes for the strands runtime seams we own."""

from __future__ import annotations

from .strands import (
    AlwaysToolModel,
    BoomModel,
    FakeMCPClient,
    FakeModel,
    FakePlugin,
    FlakyOnceModel,
    ToolThenTextModel,
    fake_plugin_factory,
)

__all__ = [
    "AlwaysToolModel",
    "BoomModel",
    "FakeMCPClient",
    "FakeModel",
    "FakePlugin",
    "FlakyOnceModel",
    "ToolThenTextModel",
    "fake_plugin_factory",
]
