"""Pipeline fixtures — worked-config directory resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_path():
    """Return a factory resolving a fixture file name to its absolute path."""

    def _resolve(name: str) -> str:
        path = FIXTURES_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"Fixture not found: {path}")
        return str(path)

    return _resolve
