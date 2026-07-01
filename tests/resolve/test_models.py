"""ModelDef -> strands Model resolution (built-in dispatch + custom import spec)."""

from __future__ import annotations

import pytest
from strands.models import Model

from strands_compose.config.resolvers.models import resolve_model
from tests.factories import model_def


def test_builtin_bedrock_provider_returns_model():
    model = resolve_model(model_def(provider="bedrock", model_id="anthropic.claude"))
    assert isinstance(model, Model)


def test_custom_provider_import_spec_returns_instance():
    model = resolve_model(model_def(provider="tests.fakes.strands:FakeModel", model_id="x"))
    assert isinstance(model, Model)


def test_custom_provider_not_a_model_subclass_raises():
    with pytest.raises(ValueError, match="Model"):
        resolve_model(model_def(provider="builtins:dict", model_id="x"))


def test_create_model_unknown_provider_raises():
    from strands_compose.models import create_model

    with pytest.raises(ValueError, match="provider"):
        create_model("nonesuch", "m")
