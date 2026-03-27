import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.services.telegram_schedule_service import (
    TelegramScheduleService,
    _as_path,
    _parse_iso,
    _safe_json_loads,
    _utcnow,
)


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.lists = {}
        self.values = {}

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = value
        return 1

    def hdel(self, key, field):
        bucket = self.hashes.get(key, {})
        existed = field in bucket
        bucket.pop(field, None)
        return 1 if existed else 0

    def lrange(self, key, start, end):
        items = self.lists.get(key, [])
        if end == -1:
            return items[start:]
        return items[start : end + 1]

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    def ltrim(self, key, start, end):
        items = self.lists.get(key, [])
        if end == -1:
            self.lists[key] = items[start:]
        else:
            self.lists[key] = items[start : end + 1]

    def set(self, key, value, ex=None, nx=False):  # noqa: ARG002
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True


def build_config(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        telegram=SimpleNamespace(
            token="123456789:abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN",
            chat_id="123456789",
            enabled=True,
            parse_mode="Markdown",
            attachment_format="txt",
            attach_responses_auto=True,
        ),
        generation=SimpleNamespace(mode="local"),
        integrations=SimpleNamespace(
            redis_url="redis://localhost:6379/15",
            selenium_remote_url="http://selenium:4444/wd/hub",
            api_url="http://api.internal:8000",
        ),
        urls=SimpleNamespace(profile_url="https://www.doctoralia.com.br/medico/teste"),
        api=SimpleNamespace(port=8000),
        data_dir=data_dir,
    )


def test_save_list_and_delete_schedule(tmp_path):
    redis_client = FakeRedis()
    service = TelegramScheduleService(
        redis_client=redis_client,
        logger=MagicMock(),
        config_loader=lambda: build_config(tmp_path),
    )

    active = service.save_schedule(
        {
            "name": "Relatorio Matinal",
            "recurrence_type": "daily",
            "time_of_day": "08:00",
            "profile_url": "https://www.doctoralia.com.br/medico/teste",
        }
    )
    paused = service.save_schedule(
        {
            "name": "Health Semanal",
            "enabled": False,
            "recurrence_type": "weekly",
            "time_of_day": "10:30",
            "day_of_week": 1,
            "report_type": "health",
        }
    )

    schedules = service.list_schedules()
    summary = service.get_summary()

    assert len(schedules) == 2
    assert {item["id"] for item in schedules} == {active["id"], paused["id"]}
    assert summary["total"] == 2
    assert summary["active"] == 1
    assert summary["paused"] == 1
    assert paused["next_run_at"] is None

    updated = service.save_schedule(
        {
            "name": "Relatorio Matinal",
            "recurrence_type": "daily",
            "time_of_day": "08:00",
            "telegram_token": None,
            "telegram_chat_id": None,
            "profile_url": None,
        },
        schedule_id=active["id"],
    )
    assert updated["telegram_token"] is None
    assert updated["telegram_chat_id"] is None
    assert updated["profile_url"] is None

    assert service.delete_schedule(paused["id"]) is True
    assert service.delete_schedule(paused["id"]) is False
    assert len(service.list_schedules()) == 1


def test_run_due_schedules_executes_past_due_entries(tmp_path):
    redis_client = FakeRedis()
    service = TelegramScheduleService(
        redis_client=redis_client,
        logger=MagicMock(),
        config_loader=lambda: build_config(tmp_path),
    )

    saved = service.save_schedule(
        {
            "name": "Execucao Imediata",
            "recurrence_type": "daily",
            "time_of_day": "09:00",
        }
    )

    stored = service.get_schedule(saved["id"])
    stored["next_run_at"] = "2000-01-01T00:00:00+00:00"
    redis_client.hset(service.schedules_key, saved["id"], json.dumps(stored))
    service.execute_schedule = MagicMock(return_value={"success": True})  # type: ignore[method-assign]

    results = service.run_due_schedules()

    assert results == [{"success": True}]
    service.execute_schedule.assert_called_once_with(saved["id"], manual=False)


def test_execute_schedule_records_history_and_attachment(tmp_path, monkeypatch):
    redis_client = FakeRedis()
    config = build_config(tmp_path)
    snapshot = {
        "doctor_name": "Dra. Ana",
        "url": "https://www.doctoralia.com.br/medico/teste",
        "average_rating": 4.8,
        "reviews": [
            {
                "id": "review-1",
                "author": "Paciente A",
                "comment": "Atendimento excelente",
                "rating": 5,
                "date": "2026-03-20",
            }
        ],
    }
    snapshot_path = config.data_dir / "20260320_dra_ana.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    class DummyNotifier:
        sent_documents = []

        def __init__(self, runtime_config, logger):  # noqa: ARG002
            self.config = runtime_config

        def validate_config(self):
            return {"valid": True, "issues": []}

        def send_document(self, file_path, caption=""):  # noqa: ARG002
            self.__class__.sent_documents.append(Path(file_path))
            return True

        def send_message(self, message):  # noqa: ARG002
            return True

    monkeypatch.setattr(
        "src.services.telegram_schedule_service.TelegramNotifier", DummyNotifier
    )

    service = TelegramScheduleService(
        redis_client=redis_client,
        logger=MagicMock(),
        config_loader=lambda: config,
    )
    monkeypatch.setattr(
        service,
        "_collect_health_snapshot",
        lambda runtime_config: {  # noqa: ARG005
            "api": {"status": "ok"},
            "redis": {"status": "ok"},
            "selenium": {"status": "ok"},
        },
    )

    saved = service.save_schedule(
        {
            "name": "Relatorio Persistido",
            "recurrence_type": "daily",
            "time_of_day": "09:30",
            "profile_url": snapshot["url"],
            "trigger_new_scrape": False,
            "include_generation": False,
            "send_attachment": True,
            "attachment_scope": "comments",
            "attachment_format": "json",
            "include_health_status": True,
        }
    )

    result = service.execute_schedule(saved["id"], manual=True)
    updated = service.get_schedule(saved["id"])
    history = service.list_history(limit=10)

    assert result["success"] is True
    assert updated["last_status"] == "sent"
    assert history[0]["status"] == "sent"
    assert history[0]["manual"] is True
    assert DummyNotifier.sent_documents
    assert DummyNotifier.sent_documents[0].exists() is True


def test_send_test_notification_handles_validation_and_success(tmp_path, monkeypatch):
    redis_client = FakeRedis()
    service = TelegramScheduleService(
        redis_client=redis_client,
        logger=MagicMock(),
        config_loader=lambda: build_config(tmp_path),
    )

    class InvalidNotifier:
        def __init__(self, runtime_config, logger):  # noqa: ARG002
            self.config = runtime_config

        def validate_config(self):
            return {"valid": False, "issues": ["Token ausente"]}

    monkeypatch.setattr(
        "src.services.telegram_schedule_service.TelegramNotifier", InvalidNotifier
    )
    invalid = service.send_test_notification()
    assert invalid["success"] is False
    assert invalid["result"]["issues"] == ["Token ausente"]

    class ValidNotifier:
        def __init__(self, runtime_config, logger):  # noqa: ARG002
            self.config = runtime_config

        def validate_config(self):
            return {"valid": True, "issues": []}

        def send_message(self, message):  # noqa: ARG002
            return True

    monkeypatch.setattr(
        "src.services.telegram_schedule_service.TelegramNotifier", ValidNotifier
    )
    valid = service.send_test_notification(message="teste")
    assert valid["success"] is True
    assert valid["result"]["sent"] is True


def test_helper_functions_and_runner_controls(tmp_path):
    redis_client = FakeRedis()
    logger = MagicMock()
    service = TelegramScheduleService(
        redis_client=redis_client,
        logger=logger,
        config_loader=lambda: build_config(tmp_path),
        poll_interval_s=0.01,
    )

    assert _parse_iso(None) is None
    assert _safe_json_loads(b'{"ok": true}') == {"ok": True}
    assert _safe_json_loads({"ok": True}) == {"ok": True}
    assert _as_path(str(tmp_path)).exists() is True
    with pytest.raises(ValueError):
        _safe_json_loads(123)

    service.run_due_schedules = MagicMock(side_effect=lambda: service._stop_event.set())  # type: ignore[method-assign]
    service.start()
    service._thread.join(timeout=1)
    assert service._stop_event.is_set() is True
    service.stop()

    class AliveThread:
        def is_alive(self):
            return True

        def join(self, timeout=5):  # noqa: ARG002
            return None

    service._thread = AliveThread()
    service.start()
    service.stop()

    service._stop_event.clear()

    def crash_once():
        service._stop_event.set()
        raise RuntimeError("loop boom")

    service.run_due_schedules = crash_once  # type: ignore[method-assign]
    service._run_loop()
    logger.error.assert_called()


def test_execute_schedule_failure_and_locking(tmp_path):
    redis_client = FakeRedis()
    service = TelegramScheduleService(
        redis_client=redis_client,
        logger=MagicMock(),
        config_loader=lambda: build_config(tmp_path),
    )

    saved = service.save_schedule(
        {
            "name": "Com Falha",
            "recurrence_type": "daily",
            "time_of_day": "07:00",
        }
    )

    with pytest.raises(ValueError):
        service.execute_schedule("missing-id")

    service._execute_schedule = MagicMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]
    failed = service.execute_schedule(saved["id"], manual=False)
    locked = service.execute_schedule(saved["id"], manual=False)
    updated = service.get_schedule(saved["id"])
    history = service.list_history(limit=5)

    assert failed["success"] is False
    assert updated["last_status"] == "failed"
    assert history[0]["status"] == "failed"
    assert locked["message"] == "Schedule already claimed by another worker"


def test_send_test_notification_overrides_and_failed_send(tmp_path, monkeypatch):
    redis_client = FakeRedis()
    service = TelegramScheduleService(
        redis_client=redis_client,
        logger=MagicMock(),
        config_loader=lambda: build_config(tmp_path),
    )
    captured = {}

    class OverrideNotifier:
        def __init__(self, runtime_config, logger):  # noqa: ARG002
            captured["token"] = runtime_config.telegram.token
            captured["chat_id"] = runtime_config.telegram.chat_id
            captured["parse_mode"] = runtime_config.telegram.parse_mode

        def validate_config(self):
            return {"valid": True, "issues": []}

        def send_message(self, message):
            captured["message"] = message
            return False

    monkeypatch.setattr(
        "src.services.telegram_schedule_service.TelegramNotifier", OverrideNotifier
    )

    result = service.send_test_notification(
        message=None,
        telegram_token="override-token",
        telegram_chat_id="@canal",
        parse_mode="invalid",
    )

    assert result["success"] is False
    assert result["message"] == "Failed to send test notification"
    assert captured["token"] == "override-token"
    assert captured["chat_id"] == "@canal"
    assert captured["parse_mode"] == ""
    assert "Teste de notificacao Doctoralia" in captured["message"]


def test_normalization_variants_and_validation_branches(tmp_path):
    redis_client = FakeRedis()
    service = TelegramScheduleService(
        redis_client=redis_client,
        logger=MagicMock(),
        config_loader=lambda: build_config(tmp_path),
    )
    now = _utcnow()

    weekdays = service._normalize_schedule(
        {
            "name": "Dias uteis",
            "recurrence_type": "weekdays",
            "time_of_day": "08:15",
        },
        existing=None,
        now=now,
    )
    assert weekdays["cron_expression"] == "15 8 * * 1-5"
    assert weekdays["recurrence_label"] == "Dias úteis às 08:15"

    interval = service._normalize_schedule(
        {
            "name": "Intervalo",
            "recurrence_type": "interval",
            "interval_minutes": 15,
        },
        existing=None,
        now=now,
    )
    assert interval["cron_expression"] is None
    assert interval["recurrence_label"] == "A cada 15 minuto(s)"

    custom = service._normalize_schedule(
        {
            "name": "Cron",
            "recurrence_type": "custom_cron",
            "cron_expression": "*/15 * * * *",
        },
        existing=None,
        now=now,
    )
    assert custom["recurrence_label"] == "Cron customizado: */15 * * * *"

    assert service._is_valid_time_of_day("23:59") is True
    assert service._is_valid_time_of_day("bad") is False
    assert service._is_valid_time_of_day("10:x") is False
    assert (
        service._build_cron_expression("weekly", "09:30", 2, None, None) == "30 9 * * 2"
    )
    assert (
        service._build_recurrence_label("weekly", "09:30", 2, None, None)
        == "Semanal (terça) às 09:30"
    )

    with pytest.raises(ValueError):
        service._build_cron_expression("custom_cron", None, None, None, None)
    with pytest.raises(ValueError):
        service._build_cron_expression("broken", "09:00", None, None, None)
    with pytest.raises(ValueError):
        service._normalize_schedule(
            {"name": "TZ", "timezone": "Invalid/Zone"},
            existing=None,
            now=now,
        )
    with pytest.raises(ValueError):
        service._normalize_schedule(
            {"name": "Hora", "time_of_day": "99:00"},
            existing=None,
            now=now,
        )
    with pytest.raises(ValueError):
        service._normalize_schedule(
            {
                "name": "Semanal",
                "recurrence_type": "weekly",
                "time_of_day": "10:00",
                "day_of_week": 9,
            },
            existing=None,
            now=now,
        )
    with pytest.raises(ValueError):
        service._normalize_schedule(
            {
                "name": "Intervalo",
                "recurrence_type": "interval",
                "interval_minutes": 1,
            },
            existing=None,
            now=now,
        )
    with pytest.raises(ValueError):
        service._normalize_schedule(
            {"name": "Report", "report_type": "bad"},
            existing=None,
            now=now,
        )
    with pytest.raises(ValueError):
        service._normalize_schedule(
            {"name": "Attach", "attachment_scope": "bad"},
            existing=None,
            now=now,
        )
    with pytest.raises(ValueError):
        service._normalize_schedule(
            {"name": "Fmt", "attachment_format": "xml"},
            existing=None,
            now=now,
        )
    with pytest.raises(ValueError):
        service._normalize_schedule(
            {"name": "Gen", "generation_mode": "bad"},
            existing=None,
            now=now,
        )
    with pytest.raises(ValueError):
        service._normalize_schedule(
            {"name": "Parse", "parse_mode": "BBCode"},
            existing=None,
            now=now,
        )


def test_snapshot_generation_and_attachment_helpers(tmp_path, monkeypatch):
    redis_client = FakeRedis()
    config = build_config(tmp_path)
    service = TelegramScheduleService(
        redis_client=redis_client,
        logger=MagicMock(),
        config_loader=lambda: config,
    )

    broken = config.data_dir / "broken.json"
    broken.write_text("{invalid", encoding="utf-8")
    mismatch = config.data_dir / "20260320_other.json"
    mismatch.write_text(
        json.dumps(
            {"url": "https://www.doctoralia.com.br/medico/outro", "reviews": []}
        ),
        encoding="utf-8",
    )
    valid = config.data_dir / "20260320_target.json"
    valid.write_text(
        json.dumps(
            {
                "doctor_name": "Dra. Ana",
                "url": "https://www.doctoralia.com.br/medico/teste",
                "reviews": [{"id": "a", "author": "Ana", "comment": "Oi"}],
            }
        ),
        encoding="utf-8",
    )

    payload, found_path = service._load_latest_snapshot(
        str(config.data_dir), "https://www.doctoralia.com.br/medico/teste"
    )
    assert payload["doctor_name"] == "Dra. Ana"
    assert found_path == valid

    with pytest.raises(FileNotFoundError):
        service._load_latest_snapshot(config.data_dir / "missing", None)

    class DummyScraper:
        def __init__(self, runtime_config, logger):  # noqa: ARG002
            self.runtime_config = runtime_config

        def scrape_reviews(self, profile_url):
            return {"doctor_name": "Novo", "url": profile_url, "reviews": []}

        def save_data(self, payload):
            saved = self.runtime_config.data_dir / "fresh.json"
            saved.write_text(json.dumps(payload), encoding="utf-8")
            return saved

    monkeypatch.setattr(
        "src.services.telegram_schedule_service.DoctoraliaScraper", DummyScraper
    )

    fresh_payload, fresh_path = service._resolve_snapshot(
        {"trigger_new_scrape": True, "profile_url": config.urls.profile_url},
        config,
    )
    assert fresh_payload["doctor_name"] == "Novo"
    assert fresh_path.name == "fresh.json"

    missing_profile_config = build_config(tmp_path)
    missing_profile_config.urls.profile_url = None
    with pytest.raises(ValueError):
        service._resolve_snapshot(
            {"trigger_new_scrape": True, "profile_url": None},
            missing_profile_config,
        )

    class EmptyScraper(DummyScraper):
        def scrape_reviews(self, profile_url):  # noqa: ARG002
            return None

    monkeypatch.setattr(
        "src.services.telegram_schedule_service.DoctoraliaScraper", EmptyScraper
    )
    with pytest.raises(RuntimeError):
        service._resolve_snapshot(
            {"trigger_new_scrape": True, "profile_url": config.urls.profile_url},
            config,
        )

    class DummyGenerator:
        def __init__(self, runtime_config, logger):  # noqa: ARG002
            self.calls = 0

        def generate_response_with_metadata(
            self, review, doctor_context, generation_mode, language  # noqa: ARG002
        ):
            if review["id"] == "explode":
                raise RuntimeError("generation failed")
            return {"text": f"Resposta para {doctor_context['name']}"}

    monkeypatch.setattr(
        "src.services.telegram_schedule_service.ResponseGenerator", DummyGenerator
    )
    reviews = [
        {"id": "ok", "author": "Ana", "comment": "Oi"},
        {"id": "skip-replied", "comment": "Ok", "doctor_reply": "já respondeu"},
        {"id": "skip-generated", "comment": "Ok", "generated_response": "existente"},
        {"id": "explode", "comment": "Ruim"},
    ]
    generated = service._generate_responses(
        reviews_data=reviews,
        doctor_data={"name": "Dra. Ana"},
        runtime_config=config,
        generation_mode="local",
        max_reviews=10,
    )
    assert len(generated) == 1
    assert reviews[0]["generated_response"] == "Resposta para Dra. Ana"

    class DummyNotifier:
        def _create_attachment_file(self, responses):
            file_path = config.data_dir / "responses.txt"
            file_path.write_text(json.dumps(responses), encoding="utf-8")
            return file_path

    responses_file = service._build_attachment(
        schedule={
            "id": "s1",
            "attachment_scope": "responses",
            "attachment_format": "txt",
        },
        runtime_config=config,
        notifier=DummyNotifier(),
        doctor_data={},
        reviews_data=[],
        generated_responses=[{"review_id": "1", "response": "ok"}],
        snapshot_payload=None,
    )
    assert responses_file.name == "responses.txt"
    assert (
        service._build_attachment(
            schedule={
                "id": "s1",
                "attachment_scope": "responses",
                "attachment_format": "txt",
            },
            runtime_config=config,
            notifier=DummyNotifier(),
            doctor_data={},
            reviews_data=[],
            generated_responses=[],
            snapshot_payload=None,
        )
        is None
    )

    comments_file = service._build_attachment(
        schedule={
            "id": "comments",
            "attachment_scope": "comments",
            "attachment_format": "csv",
        },
        runtime_config=config,
        notifier=DummyNotifier(),
        doctor_data={"name": "Dra. Ana"},
        reviews_data=[{"review_id": "1", "author": "Ana", "comment": "Oi"}],
        generated_responses=[],
        snapshot_payload=None,
    )
    snapshot_file = service._build_attachment(
        schedule={
            "id": "snapshot",
            "attachment_scope": "snapshot",
            "attachment_format": "txt",
        },
        runtime_config=config,
        notifier=DummyNotifier(),
        doctor_data={"name": "Dra. Ana"},
        reviews_data=[],
        generated_responses=[],
        snapshot_payload={"snapshot": True},
    )
    json_file = config.data_dir / "manual.json"
    txt_file = config.data_dir / "manual.txt"
    service._write_attachment(json_file, {"a": 1}, "json")
    service._write_attachment(txt_file, {"a": 1}, "txt")
    saved_snapshot = service._save_snapshot({"doctor_name": "Dr. Jose"}, config)

    assert comments_file.exists() is True
    assert snapshot_file.exists() is True
    assert json.loads(json_file.read_text(encoding="utf-8")) == {"a": 1}
    assert "RELATORIO AGENDADO DOCTORALIA" in txt_file.read_text(encoding="utf-8")
    assert "dr_jose" in saved_snapshot.name
    assert saved_snapshot.exists() is True


def test_health_snapshot_and_report_message(tmp_path, monkeypatch):
    redis_client = FakeRedis()
    config = build_config(tmp_path)
    service = TelegramScheduleService(
        redis_client=redis_client,
        logger=MagicMock(),
        config_loader=lambda: config,
    )

    class DummyResponse:
        def __init__(self, payload, status_code=200, ok=True):
            self._payload = payload
            self.status_code = status_code
            self.ok = ok

        def json(self):
            return self._payload

    class DummyRedisConn:
        def ping(self):
            return True

    def fake_requests_get(url, timeout=5):  # noqa: ARG001
        if url.endswith("/v1/ready"):
            return DummyResponse({"ready": True}, status_code=200, ok=True)
        return DummyResponse({}, status_code=503, ok=False)

    monkeypatch.setattr(
        "src.services.telegram_schedule_service.requests.get", fake_requests_get
    )
    monkeypatch.setattr(
        "src.services.telegram_schedule_service.redis.Redis.from_url",
        lambda url: DummyRedisConn(),
    )

    snapshot = service._collect_health_snapshot(config)
    assert snapshot["api"]["status"] == "ok"
    assert snapshot["redis"]["status"] == "ok"
    assert snapshot["selenium"]["status"] == "error"

    local_config = build_config(tmp_path)
    local_config.integrations.api_url = None
    local_snapshot = service._collect_health_snapshot(local_config)
    assert local_snapshot["api"] == {"status": "ok", "mode": "in-process"}

    monkeypatch.setattr(
        "src.services.telegram_schedule_service.requests.get",
        lambda url, timeout=5: (_ for _ in ()).throw(RuntimeError(f"boom:{url}")),
    )
    monkeypatch.setattr(
        "src.services.telegram_schedule_service.redis.Redis.from_url",
        lambda url: (_ for _ in ()).throw(RuntimeError("redis down")),
    )
    failed_snapshot = service._collect_health_snapshot(config)
    assert failed_snapshot["api"]["status"] == "error"
    assert failed_snapshot["redis"]["status"] == "error"
    assert failed_snapshot["selenium"]["status"] == "error"

    message = service._build_report_message(
        schedule={
            "name": "Resumo Completo",
            "report_type": "complete",
            "include_health_status": True,
            "profile_label": "Perfil Principal",
        },
        doctor_data={"name": "Dra. Ana", "rating": 4.8},
        reviews_data=[
            {"author": "Ana", "comment": "Excelente atendimento e muito cuidado."},
            {"author": "Bruno", "comment": "Consulta objetiva."},
        ],
        generated_responses=[{"response": "Obrigada"}],
        health_snapshot={
            "api": {"status": "ok"},
            "redis": {"status": "ok"},
            "selenium": {"status": "ok"},
        },
        snapshot_path=config.data_dir / "snapshot.json",
    )
    health_message = service._build_report_message(
        schedule={
            "name": "Health",
            "report_type": "health",
            "include_health_status": False,
        },
        doctor_data={},
        reviews_data=[],
        generated_responses=[],
        health_snapshot={},
        snapshot_path=None,
    )

    assert "🤖 Respostas geradas: 1" in message
    assert "*Prévia operacional*" in message
    assert "🛠️ Relatório focado em saúde operacional." in health_message
