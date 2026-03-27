from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

from src.telegram_notifier import TelegramNotifier


class DummyResponse:
    def __init__(self, status_code=200, text="OK", headers=None, payload=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self._payload = payload or {}

    def json(self):
        return self._payload


def build_notifier(tmp_path, **telegram_overrides):
    telegram = SimpleNamespace(
        enabled=True,
        token="123456789:" + ("A" * 40),
        chat_id="123456",
        parse_mode="Markdown",
        attach_responses_auto=False,
        attachment_format="txt",
    )
    for key, value in telegram_overrides.items():
        setattr(telegram, key, value)

    config = SimpleNamespace(data_dir=tmp_path, telegram=telegram)
    logger = MagicMock()
    return TelegramNotifier(config, logger), logger


def sample_responses():
    return [
        {
            "author": "Ana",
            "date": "2026-03-25T10:30:00-03:00",
            "rating": 5,
            "review_id": "rev-1",
            "comment": "Excelente atendimento",
            "response": "Muito obrigada pela confianca.",
        }
    ]


def test_get_parse_mode_handles_invalid_value_and_attribute_errors(tmp_path):
    notifier, _ = build_notifier(tmp_path, parse_mode="invalid")
    assert notifier._get_parse_mode() == ""

    notifier.config.telegram = None
    assert notifier._get_parse_mode() == ""


def test_send_message_returns_false_when_disabled(tmp_path):
    notifier, logger = build_notifier(tmp_path, enabled=False)

    assert notifier.send_message("mensagem") is False
    logger.debug.assert_called_once()


def test_send_message_retries_request_exception_and_then_succeeds(
    monkeypatch, tmp_path
):
    notifier, _ = build_notifier(tmp_path)
    calls = {"count": 0}

    def fake_post(url, data=None, timeout=0):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.RequestException("temporary network issue")
        return DummyResponse(200)

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("time.sleep", lambda _: None)

    assert notifier.send_message("Mensagem de teste") is True
    assert calls["count"] == 2


def test_send_message_timeout_final_failure(monkeypatch, tmp_path):
    notifier, logger = build_notifier(tmp_path)

    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.Timeout()),
    )
    monkeypatch.setattr("time.sleep", lambda _: None)

    assert notifier.send_message("Mensagem de teste", retry_count=1) is False
    logger.error.assert_called_once()


def test_send_document_parse_mode_fallback_rewinds_file_before_retry(
    monkeypatch, tmp_path
):
    notifier, _ = build_notifier(tmp_path)
    file_path = tmp_path / "payload.txt"
    file_path.write_text("conteudo original", encoding="utf-8")
    payloads = []

    def fake_post(url, files=None, data=None, timeout=0):
        payloads.append(files["document"].read())
        if len(payloads) == 1:
            return DummyResponse(400, text="Bad Request")
        return DummyResponse(200)

    monkeypatch.setattr("requests.post", fake_post)

    assert notifier.send_document(file_path, caption="Legenda _com markdown_") is True
    assert payloads == [b"conteudo original", b"conteudo original"]


def test_send_document_request_exception_final_failure(monkeypatch, tmp_path):
    notifier, logger = build_notifier(tmp_path)
    file_path = tmp_path / "payload.txt"
    file_path.write_text("conteudo original", encoding="utf-8")

    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            requests.RequestException("network down")
        ),
    )
    monkeypatch.setattr("time.sleep", lambda _: None)

    assert notifier.send_document(file_path, retry_count=1) is False
    logger.error.assert_called_once()


def test_create_attachment_file_supports_json_csv_and_txt_formats(tmp_path):
    notifier_json, _ = build_notifier(tmp_path, attachment_format="json")
    json_path = notifier_json._create_attachment_file(sample_responses())
    assert json_path is not None
    assert json_path.suffix == ".json"
    assert json_path.read_text(encoding="utf-8")

    notifier_csv, _ = build_notifier(tmp_path, attachment_format="csv")
    csv_path = notifier_csv._create_attachment_file(sample_responses())
    assert csv_path is not None
    csv_content = csv_path.read_text(encoding="utf-8")
    assert "author,date,rating,review_id,comment,response" in csv_content

    notifier_txt, _ = build_notifier(tmp_path, attachment_format="yaml")
    txt_path = notifier_txt._create_attachment_file(sample_responses())
    assert txt_path is not None
    txt_content = txt_path.read_text(encoding="utf-8")
    assert "RESPOSTAS DOCTORALIA" in txt_content
    assert "Excelente atendimento" in txt_content


def test_create_attachment_file_handles_invalid_date_and_empty_input(tmp_path):
    notifier, _ = build_notifier(tmp_path)

    assert notifier._create_attachment_file([]) is None

    file_path = notifier._create_attachment_file(
        [
            {
                "author": "Paciente",
                "date": "not-a-date",
                "rating": "",
                "review_id": "rev-1",
                "comment": "Bom",
                "response": "Obrigada!",
            }
        ]
    )
    assert file_path is not None
    assert "not-a-date"[:10] in file_path.read_text(encoding="utf-8")


def test_send_responses_generated_prefers_document_when_auto_attach_enabled(tmp_path):
    notifier, _ = build_notifier(tmp_path, attach_responses_auto=True)
    attachment = tmp_path / "responses.txt"
    attachment.write_text("dados", encoding="utf-8")

    with patch.object(notifier, "_create_attachment_file", return_value=attachment):
        with patch.object(
            notifier, "send_document", return_value=True
        ) as send_document:
            with patch.object(
                notifier,
                "send_message",
                return_value=False,
            ) as send_message:
                assert notifier.send_responses_generated(sample_responses()) is True

    send_document.assert_called_once()
    send_message.assert_not_called()


def test_send_responses_generated_falls_back_to_message_when_attachment_missing(
    tmp_path,
):
    notifier, _ = build_notifier(tmp_path, attach_responses_auto=True)

    with patch.object(notifier, "_create_attachment_file", return_value=None):
        with patch.object(notifier, "send_message", return_value=True) as send_message:
            assert notifier.send_responses_generated(sample_responses()) is True

    send_message.assert_called_once()


def test_high_level_notification_helpers_delegate_to_message_or_document(tmp_path):
    notifier, _ = build_notifier(tmp_path, attach_responses_auto=False)
    attachment = tmp_path / "responses.txt"
    attachment.write_text("dados", encoding="utf-8")

    with patch.object(notifier, "send_message", return_value=True) as send_message:
        with patch.object(
            notifier, "send_document", return_value=True
        ) as send_document:
            assert notifier.send_scraping_complete(
                {"doctor_name": "Dra. Ana"}, attachment
            )
            assert notifier.send_responses_with_file(sample_responses(), attachment)
            assert notifier.send_error("falha")
            assert notifier.send_daemon_started(15)
            assert notifier.send_daemon_stopped()
            assert notifier.send_generation_cycle_success(sample_responses())
            assert notifier.send_generation_cycle_no_responses()
            assert notifier.send_daemon_error("erro")
            assert notifier.send_custom_message("Titulo", "Conteudo")

    assert send_message.call_count == 8
    send_document.assert_called_once()


def test_test_connection_handles_success_and_errors(monkeypatch, tmp_path):
    notifier, logger = build_notifier(tmp_path)

    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: DummyResponse(
            200, payload={"ok": True, "result": {"first_name": "Doctoralia Bot"}}
        ),
    )
    assert notifier.test_connection() is True

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: DummyResponse(500))
    assert notifier.test_connection() is False

    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            requests.RequestException("offline")
        ),
    )
    assert notifier.test_connection() is False

    assert logger.info.called
    assert logger.error.called


def test_validate_config_accepts_channel_ids_and_reports_invalid_values(tmp_path):
    notifier, _ = build_notifier(tmp_path, chat_id="@canal-das-notificacoes")
    valid = notifier.validate_config()
    assert valid["valid"] is True
    assert valid["issues"] == []

    notifier_bad, _ = build_notifier(tmp_path, token="curto", chat_id="chat-ruim")
    invalid = notifier_bad.validate_config()
    assert invalid["valid"] is False
    assert "Token do bot parece inválido (muito curto)" in invalid["issues"]
    assert "Formato do Chat ID inválido" in invalid["issues"]
