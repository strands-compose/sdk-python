"""LLM model factory."""

from __future__ import annotations

from typing import Any

from strands.models import Model

PROVIDERS = ("bedrock", "ollama", "openai", "gemini", "anthropic")


def _missing_extra_error(provider: str, extra: str) -> ImportError:
    """Build the ``ImportError`` raised when an optional provider extra is missing.

    Args:
        provider: Provider name as passed to ``create_model``, e.g. ``"openai"``.
        extra: Name of the pip extra that supplies the dependency, e.g.
            ``"openai"``. Usually matches ``provider`` but need not.

    Returns:
        An ``ImportError`` with install instructions for the missing extra.
    """
    return ImportError(
        f"The '{provider}' provider requires the {extra} extra:\n"
        f"  pip install strands-compose[{extra}]\n"
        f"Or install directly: pip install strands-agents[{extra}]"
    )


def create_model(provider: str, model_id: str, **params: Any) -> Model:
    """Dispatch to the appropriate model factory by provider name.

    Args:
        provider: ``"bedrock"``, ``"anthropic"``, ``"ollama"``, ``"openai"``, ``"gemini"``.
        model_id: Model identifier.
        **params: Provider-specific keyword arguments.

    Returns:
        Strands model instance.

    Raises:
        ValueError: If the provider is unknown.
        ImportError: If a required optional provider package is not installed.
    """
    provider_name = provider.lower()
    if provider_name == "bedrock":
        from strands.models.bedrock import BedrockModel

        return BedrockModel(model_id=model_id, **params)

    if provider_name == "ollama":
        try:
            from strands.models.ollama import OllamaModel
        except ImportError:
            raise _missing_extra_error("ollama", "ollama") from None
        return OllamaModel(model_id=model_id, **params)

    if provider_name == "openai":
        try:
            from strands.models.openai import OpenAIModel
        except ImportError:
            raise _missing_extra_error("openai", "openai") from None
        return OpenAIModel(model_id=model_id, **params)

    if provider_name == "gemini":
        try:
            from strands.models.gemini import GeminiModel
        except ImportError:
            raise _missing_extra_error("gemini", "gemini") from None
        return GeminiModel(model_id=model_id, **params)

    if provider_name == "anthropic":
        try:
            from strands.models.anthropic import AnthropicModel
        except ImportError:
            raise _missing_extra_error("anthropic", "anthropic") from None
        return AnthropicModel(model_id=model_id, **params)

    raise ValueError(f"Unknown model provider '{provider}'.\nAvailable: {', '.join(PROVIDERS)}.")
