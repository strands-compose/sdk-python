"""Resolve ModelDef -> strands model instance."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from strands.models import Model

from ...models import PROVIDERS, create_model
from ...utils import load_object

if TYPE_CHECKING:
    from ..schema import ModelDef

logger = logging.getLogger(__name__)


def resolve_model(model_def: ModelDef) -> Model:
    """Resolve a ModelDef to a strands model instance.

    Built-in providers (``"ollama"``, ``"bedrock"``, ``"openai"``,
    ``"gemini"``) are dispatched via :func:`~strands_compose.models.create_model`.
    Any other ``provider`` value is treated as an import spec
    (``module.path:ClassName``) for a custom :class:`~strands.models.Model`
    subclass.

    Args:
        model_def: Parsed model definition from YAML.

    Returns:
        A strands-compatible model instance.

    Raises:
        ValueError: If the custom model class is not a Model subclass.
        ImportError: If a required optional provider package is not installed.
    """
    if model_def.provider.lower() in {p.lower() for p in PROVIDERS}:
        return create_model(model_def.provider, model_def.model_id, **model_def.params)

    # Custom provider — load class from import spec
    model_cls = load_object(model_def.provider, target="model class")
    if not issubclass(model_cls, Model):
        raise ValueError(
            f"Custom model class '{model_def.provider}' must be a subclass of strands.models.Model."
        )
    return model_cls(model_id=model_def.model_id, **model_def.params)
