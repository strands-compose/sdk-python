"""Tests for core.config.resolvers.models — resolve_model."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from strands.models import Model

from strands_compose.config.resolvers.models import resolve_model
from strands_compose.config.schema import ModelDef


class TestResolveModel:
    @patch("strands.models.bedrock.BedrockModel")
    def test_bedrock_model(self, mock_bedrock):
        model_def = ModelDef(provider="bedrock", model_id="us.amazon.nova-pro-v1:0")
        resolve_model(model_def)
        mock_bedrock.assert_called_once()

    @patch("strands.models.ollama.OllamaModel")
    def test_ollama_model(self, mock_ollama):
        model_def = ModelDef(provider="ollama", model_id="llama3")
        resolve_model(model_def)
        mock_ollama.assert_called_once()

    @patch("strands_compose.config.resolvers.models.load_object")
    def test_custom_model_class(self, mock_import):
        class CustomModel(Model):
            def __init__(self, **kwargs):
                pass

            def update_config(self, **kwargs):
                pass

            def get_config(self):
                return {}

            def stream(self, *args, **kwargs):
                yield from ()

            def structured_output(self, *args, **kwargs):
                return None

        mock_import.return_value = CustomModel
        model_def = ModelDef(provider="my.module:CustomModel", model_id="custom-v1")
        result = resolve_model(model_def)
        assert isinstance(result, Model)

    @patch("strands_compose.config.resolvers.models.load_object")
    def test_custom_model_not_subclass_raises(self, mock_import):
        mock_import.return_value = str  # str is not a Model subclass
        model_def = ModelDef(provider="my.module:NotAModel", model_id="bad")
        with pytest.raises(ValueError, match="must be a subclass"):
            resolve_model(model_def)

    @patch(
        "strands_compose.config.resolvers.models.create_model",
        side_effect=RuntimeError("connection failed"),
    )
    def test_generic_exception_propagates(self, mock_create):
        model_def = ModelDef(provider="bedrock", model_id="bad-model")
        with pytest.raises(RuntimeError, match="connection failed"):
            resolve_model(model_def)
