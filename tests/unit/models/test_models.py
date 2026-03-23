"""Tests for core.models — create_model, create_bedrock_model, create_ollama_model."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from strands_compose.models import create_model


class TestCreateModel:
    @patch("strands.models.bedrock.BedrockModel")
    def test_bedrock_dispatch(self, mock_bedrock):
        create_model("bedrock", "us.amazon.nova-pro-v1:0")
        mock_bedrock.assert_called_once()

    @patch("strands.models.ollama.OllamaModel")
    def test_ollama_dispatch(self, mock_ollama):
        create_model("ollama", "llama3")
        mock_ollama.assert_called_once()

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown model provider"):
            create_model("gpt", "gpt-4")

    @patch("strands.models.bedrock.BedrockModel")
    def test_case_insensitive(self, mock_bedrock: MagicMock) -> None:
        create_model("Bedrock", "model-id")
        mock_bedrock.assert_called_once()


class TestFriendlyImportErrors:
    """Verify that missing optional provider packages raise friendly ImportErrors."""

    def test_ollama_missing_raises_friendly_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ImportError for ollama includes the correct pip install command."""
        monkeypatch.setitem(sys.modules, "strands.models.ollama", None)
        with pytest.raises(ImportError, match=r"pip install strands-compose\[ollama\]"):
            create_model("ollama", "llama3")

    def test_openai_missing_raises_friendly_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ImportError for openai includes the correct pip install command."""
        monkeypatch.setitem(sys.modules, "strands.models.openai", None)
        with pytest.raises(ImportError, match=r"pip install strands-compose\[openai\]"):
            create_model("openai", "gpt-4")

    def test_gemini_missing_raises_friendly_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ImportError for gemini includes the correct pip install command."""
        monkeypatch.setitem(sys.modules, "strands.models.gemini", None)
        with pytest.raises(ImportError, match=r"pip install strands-compose\[gemini\]"):
            create_model("gemini", "gemini-pro")

    def test_ollama_error_message_contains_install_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ollama ImportError message also mentions strands-agents fallback install."""
        monkeypatch.setitem(sys.modules, "strands.models.ollama", None)
        with pytest.raises(ImportError, match=r"strands-agents\[ollama\]"):
            create_model("ollama", "llama3")
