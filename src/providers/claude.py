"""Provedor Anthropic Claude (Messages API)."""

from __future__ import annotations

from typing import Any, Dict

import requests

from src.providers.base import AIProvider, ProviderError


class ClaudeProvider(AIProvider):
    name = "claude"

    @staticmethod
    def _extract_text(payload: Dict[str, Any]) -> str:
        for item in payload.get("content", []):
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
        api_key = getattr(config, "claude_api_key", None)
        model = getattr(config, "claude_model", "claude-3-5-sonnet-latest")
        if not api_key:
            raise ProviderError("Claude API key não configurada")

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=45,
            )
        except requests.exceptions.Timeout:
            raise ProviderError("Claude timeout após 45s")
        except requests.exceptions.ConnectionError:
            raise ProviderError("Claude erro de conexão")
        except requests.exceptions.RequestException as e:
            raise ProviderError(f"Claude erro de rede: {e}")

        if not response.ok:
            raise ProviderError(
                f"Claude retornou {response.status_code}: {response.text[:300]}"
            )

        try:
            data = response.json()
        except (ValueError, KeyError):
            raise ProviderError("Claude retornou resposta inválida (não-JSON)")

        text = self._extract_text(data)
        if not text:
            raise ProviderError("Claude não retornou texto de resposta")
        return text, str(model)
