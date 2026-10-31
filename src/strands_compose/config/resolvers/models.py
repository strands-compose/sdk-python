"""Resolve ModelDef -> strands model instance."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from strands.models import CacheConfig, Model

from ...models import PROVIDERS, create_model
from ...utils import load_object

if TYPE_CHECKING:
    from ..schema import CacheDef, ModelDef

logger = logging.getLogger(__name__)

# Built-in providers whose model config has no ``cache_config`` key.
# Strands would warn about it as an invalid parameter, so ``cache`` is not passed to them.
_PROVIDERS_WITHOUT_CACHE = frozenset({"gemini"})


def _resolve_cache(cache: bool | CacheDef | None) -> CacheConfig | None:
    """Turn a ``ModelDef.cache`` value into strands' ``CacheConfig``.

    Args:
        cache: ``None`` or ``False`` (off), ``True`` (automatic caching), or a
            validated :class:`CacheDef`.

    Returns:
        A ``CacheConfig``, or ``None`` when caching is off.
    """
    if cache is None or cache is False:
        return None
    if cache is True:
        return CacheConfig()
    return CacheConfig(**cache.model_dump(exclude_unset=True))


def resolve_model(model_def: ModelDef) -> Model:
    """Resolve a ModelDef to a strands model instance.

    Built-in providers (``"bedrock"``, ``"anthropic"``, ``"ollama"``,
    ``"openai"``, ``"gemini"``) are dispatched via
    :func:`~strands_compose.models.create_model`.
    Any other ``provider`` value is treated as an import spec
    (``module.path:ClassName``) for a custom :class:`~strands.models.Model`
    subclass.

    ``cache`` becomes a ``cache_config=CacheConfig(...)`` keyword argument for
    built-in and custom providers. It is not passed when caching is off, nor to
    ``gemini``, whose model has no ``cache_config``.

    Args:
        model_def: Parsed model definition from YAML.

    Returns:
        A strands-compatible model instance.

    Raises:
        TypeError: If the custom model class is not a Model subclass.
        ImportError: If a required optional provider package is not installed.
    """
    params = dict(model_def.params)
    cache_config = _resolve_cache(model_def.cache)
    if cache_config is not None:
        if model_def.provider.lower() in _PROVIDERS_WITHOUT_CACHE:
            logger.debug(
                "model=<%s>, provider=<%s> | provider has no cache_config, cache not passed",
                model_def.model_id,
                model_def.provider,
            )
        else:
            params["cache_config"] = cache_config

    if model_def.provider.lower() in {p.lower() for p in PROVIDERS}:
        return create_model(model_def.provider, model_def.model_id, **params)

    # Custom provider — load class from import spec
    model_cls = load_object(model_def.provider, target="model class")
    if not issubclass(model_cls, Model):
        raise TypeError(
            f"Custom model class '{model_def.provider}' must be a subclass of strands.models.Model."
        )
    return model_cls(model_id=model_def.model_id, **params)
