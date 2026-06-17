"""
Provedores de IA para geração de respostas.

Cada provedor encapsula a chamada HTTP a um serviço de terceiros (OpenAI,
Google Gemini, Anthropic Claude) e a extração do texto da resposta, expondo a
mesma interface `AIProvider`. O `ResponseGenerator` permanece focado em
templates e orquestração, delegando a chamada externa ao provedor adequado.
"""

from __future__ import annotations

from typing import Any, Dict, Type

from src.providers.base import AIProvider, ProviderError
from src.providers.claude import ClaudeProvider
from src.providers.gemini import GeminiProvider
from src.providers.openai import OpenAIProvider

# Mapa de modo de geração -> classe do provedor.
_PROVIDERS: Dict[str, Type[AIProvider]] = {
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
}


def get_provider(mode: str, config: Any) -> AIProvider:
    """Retorna a instância de provedor para o modo de geração informado.

    Args:
        mode: "openai", "gemini" ou "claude".
        config: objeto de configuração de geração (lido pelo provedor).

    Raises:
        ProviderError: se o modo não corresponder a um provedor conhecido.
    """
    provider_cls = _PROVIDERS.get(mode)
    if provider_cls is None:
        raise ProviderError(f"Modo de geração inválido: {mode}")
    return provider_cls(config)


__all__ = [
    "AIProvider",
    "ProviderError",
    "OpenAIProvider",
    "GeminiProvider",
    "ClaudeProvider",
    "get_provider",
]
