"""LLM model factory."""

from __future__ import annotations

from typing import Any

from strands.models import Model

PROVIDERS = ("bedrock", "ollama", "openai", "gemini", "anthropic")


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
            raise ImportError(
                "The 'ollama' provider requires the ollama extra:\n"
                "  pip install strands-compose[ollama]\n"
                "Or install directly: pip install strands-agents[ollama]"
            ) from None
        return OllamaModel(model_id=model_id, **params)

    if provider_name == "openai":
        try:
            from strands.models.openai import OpenAIModel
        except ImportError:
            raise ImportError(
                "The 'openai' provider requires the openai extra:\n"
                "  pip install strands-compose[openai]\n"
                "Or install directly: pip install strands-agents[openai]"
            ) from None
        return OpenAIModel(model_id=model_id, **params)

    if provider_name == "gemini":
        try:
            from strands.models.gemini import GeminiModel
        except ImportError:
            raise ImportError(
                "The 'gemini' provider requires the gemini extra:\n"
                "  pip install strands-compose[gemini]\n"
                "Or install directly: pip install strands-agents[gemini]"
            ) from None
        return GeminiModel(model_id=model_id, **params)

    if provider_name == "anthropic":
        try:
            from strands.models.anthropic import AnthropicModel
        except ImportError:
            raise ImportError(
                "The 'anthropic' provider requires the anthropic extra:\n"
                "  pip install strands-compose[anthropic]\n"
                "Or install directly: pip install strands-agents[anthropic]"
            ) from None
        return AnthropicModel(model_id=model_id, **params)

    raise ValueError(f"Unknown model provider '{provider}'.\nAvailable: {', '.join(PROVIDERS)}.")
