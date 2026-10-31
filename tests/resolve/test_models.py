"""ModelDef -> strands Model resolution (built-in dispatch + custom import spec)."""

from __future__ import annotations

import pytest
from strands.models import CacheConfig, Model

from strands_compose.config.resolvers.models import resolve_model
from tests.factories import model_def


def test_builtin_bedrock_provider_returns_model():
    model = resolve_model(model_def(provider="bedrock", model_id="anthropic.claude"))
    assert isinstance(model, Model)


def test_custom_provider_import_spec_returns_instance():
    model = resolve_model(model_def(provider="tests.fakes.strands:FakeModel", model_id="x"))
    assert isinstance(model, Model)


def test_custom_provider_not_a_model_subclass_raises():
    with pytest.raises(TypeError, match="Model"):
        resolve_model(model_def(provider="builtins:dict", model_id="x"))


def test_create_model_unknown_provider_raises():
    from strands_compose.models import create_model

    with pytest.raises(ValueError, match="provider"):
        create_model("nonesuch", "m")


def test_cache_true_enables_automatic_caching():
    model = resolve_model(model_def(provider="bedrock", model_id="anthropic.claude", cache=True))

    cache = model.get_config()["cache_config"]
    assert isinstance(cache, CacheConfig)
    assert cache.strategy == "auto"


def test_cache_mapping_sets_cache_config_fields():
    model = resolve_model(
        model_def(
            provider="bedrock",
            model_id="anthropic.claude",
            cache={"strategy": "auto", "ttl": "1h"},
        )
    )

    cache = model.get_config()["cache_config"]
    assert isinstance(cache, CacheConfig)
    assert cache.ttl == "1h"


@pytest.mark.parametrize("cache", [None, False])
def test_cache_off_passes_no_cache_config(cache):
    model = resolve_model(model_def(provider="bedrock", model_id="anthropic.claude", cache=cache))

    assert model.get_config().get("cache_config") is None


def test_cache_is_not_passed_to_gemini():
    model = resolve_model(model_def(provider="gemini", model_id="gemini-x", cache=True))

    assert "cache_config" not in model.get_config()


def test_custom_provider_receives_cache_config_only_when_cache_is_set():
    cached = resolve_model(
        model_def(provider="tests.fakes.strands:FakeModel", model_id="x", cache=True)
    )
    plain = resolve_model(model_def(provider="tests.fakes.strands:FakeModel", model_id="x"))

    assert isinstance(cached.get_config()["cache_config"], CacheConfig)
    assert "cache_config" not in plain.get_config()
