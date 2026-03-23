"""Export completeness tests for strands_compose top-level package."""

from __future__ import annotations

import pytest

import strands_compose


class TestTopLevelExports:
    """Verify that the public API surface is complete."""

    def test_all_names_are_accessible(self) -> None:
        """Every name in __all__ must be reachable as an attribute."""
        for name in strands_compose.__all__:
            assert hasattr(strands_compose, name), f"{name!r} in __all__ but not accessible"

    @pytest.mark.parametrize(
        "name",
        ["ToolNameSanitizer", "MaxToolCallsGuard", "StopGuard", "EventPublisher"],
    )
    def test_key_exports_in_all(self, name: str) -> None:
        """Key public classes must appear in __all__ and be importable."""
        assert name in strands_compose.__all__
        assert getattr(strands_compose, name) is not None
