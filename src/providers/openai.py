"""Provedor OpenAI (Chat Completions)."""

from __future__ import annotations

from typing import Any, Dict

import requests

from src.providers.base import AIProvider, ProviderError


class OpenAIProvider(AIProvider):
    name = "openai"

    @staticmethod
    def _extract_text(payload: Dict[str, Any]) -> str:
        choices = payload.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    return str(item.get("text") or "").strip()
        return ""

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, str]:
        config = self.config
        api_key = getattr(config, "openai_api_key", None)
        model = getattr(config, "openai_model", "gpt-4.1-mini")
        if not api_key:
            raise ProviderError("OpenAI API key não configurada")

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=45,
            )
        except requests.exceptions.Timeout:
            raise ProviderError("OpenAI timeout após 45s")
        except requests.exceptions.ConnectionError:
            raise ProviderError("OpenAI erro de conexão")
        except requests.exceptions.RequestException as e:
            raise ProviderError(f"OpenAI erro de rede: {e}")

        if not response.ok:
            raise ProviderError(
                f"OpenAI retornou {response.status_code}: {response.text[:300]}"
            )

        try:
            data = response.json()
        except (ValueError, KeyError):
            raise ProviderError("OpenAI retornou resposta inválida (não-JSON)")

        text = self._extract_text(data)
        if not text:
            raise ProviderError("OpenAI não retornou texto de resposta")
        return text, str(model)
