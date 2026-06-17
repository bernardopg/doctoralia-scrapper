"""Interface comum dos provedores de IA."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


# Herdar de ValueError mantém compatibilidade com o tratamento de erros
# anterior do ResponseGenerator, que sinalizava falhas de provedor via
# ValueError. Código existente que captura ValueError continua funcionando.
class ProviderError(ValueError):
    """Erro ao chamar um provedor de IA (config ausente, rede, resposta inválida)."""


class AIProvider(ABC):
    """Contrato de um provedor de geração de texto por IA."""

    #: Nome curto do provedor (ex.: "openai").
    name: str = "base"

    def __init__(self, config: Any) -> None:
        # `config` é o objeto de configuração de geração (generation config),
        # de onde cada provedor lê sua API key e modelo.
        self.config = config

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, str]:
        """Gera texto a partir do prompt.

        Returns:
            (texto_gerado, nome_do_modelo)

        Raises:
            ProviderError: se a API key faltar, houver erro de rede ou a
            resposta for inválida/vazia.
        """
        raise NotImplementedError
