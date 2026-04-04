import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telegram_notifier import TelegramNotifier


class DummyResponse:
    def __init__(self, status_code=200, text="OK", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


@pytest.fixture
def notifier():
    mock_config = types.SimpleNamespace()
    mock_config.telegram = types.SimpleNamespace(
        enabled=True, token="bot123456789:ABC", chat_id="123456"
    )
    return TelegramNotifier(mock_config, MagicMock())


def test_sanitize_markdown_private(notifier):
    raw = "Hello _world_ **bold** (test)!"
    # Accessing the private method intentionally for coverage
    sanitized = notifier._sanitize_markdown(raw)
    # Ensure underscores are escaped but bold preserved
    assert "**bold**" in sanitized
    assert "_world_" not in sanitized  # It should become escaped
    assert "(test)!" in sanitized


def test_sanitize_markdown_preserves_plain_dots_and_inline_code_in_markdown(notifier):
    raw = (
        "📁 Snapshot: `20260403_224727_bruna_pinto_gomes.json`\n"
        "• I.N: Uma excelente médica."
    )

    sanitized = notifier._sanitize_markdown(raw, parse_mode="Markdown")

    assert "`20260403_224727_bruna_pinto_gomes.json`" in sanitized
    assert "I.N: Uma excelente médica." in sanitized
    assert "\\." not in sanitized
    assert "\\_" not in sanitized


def test_sanitize_markdownv2_keeps_escaping_special_characters(notifier):
    raw = "Arquivo final: relatorio_01.json."

    sanitized = notifier._sanitize_markdown(raw, parse_mode="MarkdownV2")

    assert "relatorio\\_01\\.json\\." in sanitized


def test_send_message_rate_limit_then_success(monkeypatch, notifier):
    calls = {"n": 0}

    def fake_post(url, data=None, timeout=0):  # noqa: D401
        calls["n"] += 1
        if calls["n"] == 1:
            return DummyResponse(status_code=429, headers={"Retry-After": "0"})
        return DummyResponse(200)

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("time.sleep", lambda _: None)

    assert notifier.send_message("Test message") is True
    assert calls["n"] == 2  # One retry


def test_send_message_markdown_fallback(monkeypatch, notifier):
    calls = {"n": 0}

    def fake_post(url, data=None, timeout=0):  # noqa: D401
        calls["n"] += 1
        if calls["n"] == 1:
            return DummyResponse(status_code=400, text="Bad Request")
        return DummyResponse(200)

    monkeypatch.setattr("requests.post", fake_post)
    assert notifier.send_message("Message with _markdown_") is True
    assert calls["n"] == 2


def test_send_document_file_not_found(monkeypatch, notifier):
    # Ensure a 404 path
    monkeypatch.setattr("requests.post", lambda *a, **k: DummyResponse(200))
    assert notifier.send_document(Path("/non/existent/file.txt")) is False
