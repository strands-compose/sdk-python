"""Shared fixtures for integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the integration test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def fixture_path():
    """Return a factory that resolves a fixture name to its full path."""

    def _resolve(name: str) -> str:
        path = FIXTURES_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"Fixture not found: {path}")
        return str(path)

    return _resolve
