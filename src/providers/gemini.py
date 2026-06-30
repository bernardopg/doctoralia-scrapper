"""Provedor Google Gemini (generateContent)."""

from __future__ import annotations

from typing import Any, Dict

import requests

from src.providers.base import AIProvider, ProviderError


class GeminiProvider(AIProvider):
    name = "gemini"

    @staticmethod
    def _extract_text(payload: Dict[str, Any]) -> str:
        candidates = payload.get("candidates", [])
        if not candidates:
            return ""
        content = candidates[0].get("content", {})
        for part in content.get("parts", []):
            if isinstance(part, dict) and part.get("text"):
                return str(part["text"]).strip()
        return ""

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, str]:
        config = self.config
        api_key = getattr(config, "gemini_api_key", None)
        model = getattr(config, "gemini_model", "gemini-2.5-flash")
        if not api_key:
            raise ProviderError("Gemini API key não configurada")

        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                json={
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens,
                    },
                },
                timeout=45,
            )
        except requests.exceptions.Timeout:
            raise ProviderError("Gemini timeout após 45s")
        except requests.exceptions.ConnectionError:
            raise ProviderError("Gemini erro de conexão")
        except requests.exceptions.RequestException as e:
            raise ProviderError(f"Gemini erro de rede: {e}")

        if not response.ok:
            raise ProviderError(
                f"Gemini retornou {response.status_code}: {response.text[:300]}"
            )

        try:
            data = response.json()
        except (ValueError, KeyError):
            raise ProviderError("Gemini retornou resposta inválida (não-JSON)")

        text = self._extract_text(data)
        if not text:
            raise ProviderError("Gemini não retornou texto de resposta")
        return text, str(model)
