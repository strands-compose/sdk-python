"""Root conftest — registers markers so they are available to all test layers."""

from tests.unit.conftest import *  # noqa: F401, F403 — re-export shared fixtures


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: Integration tests (full pipeline)")
    config.addinivalue_line("markers", "ollama: Tests requiring local Ollama")
    config.addinivalue_line("markers", "bedrock: Tests requiring AWS Bedrock")
