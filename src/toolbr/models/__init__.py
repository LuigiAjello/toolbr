"""Escolha do modelo pelo nome.

oracle | naive | vulnerable | cautious      modelos de teste, sem API
claude-...  ou  anthropic:<id>              Anthropic
gpt-... / o3... ou  openai:<id>             OpenAI
ollama:<id>                                 modelo aberto local via Ollama
"""

from __future__ import annotations

from toolbr.models.mock import TEST_MODELS


def make_model(spec: str, temperature: float | None = None, effort: str | None = None):
    if spec in TEST_MODELS:
        return TEST_MODELS[spec]()
    provider, _, model_id = spec.partition(":")
    if not model_id:
        model_id = spec
        if spec.startswith("claude"):
            provider = "anthropic"
        elif spec.startswith(("gpt", "o1", "o3", "o4")):
            provider = "openai"
        else:
            raise ValueError(f"não sei o provedor de {spec!r}: use anthropic:, openai: ou ollama:")
    if provider == "anthropic":
        from toolbr.models.anthropic_model import AnthropicModel

        return AnthropicModel(model_id, temperature=temperature, effort=effort)
    if provider in ("openai", "ollama"):
        from toolbr.models.openai_model import OpenAIModel

        return OpenAIModel(model_id, provider=provider, temperature=temperature, effort=effort)
    raise ValueError(f"provedor desconhecido: {provider}")
