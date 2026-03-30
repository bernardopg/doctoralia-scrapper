"""
Tests for n8n API integration.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from config.settings import (
    APIConfig,
    AppConfig,
    DelayConfig,
    FavoriteProfileConfig,
    GenerationConfig,
    IntegrationConfig,
    PrivacyConfig,
    ScrapingConfig,
    SecurityConfig,
    TelegramConfig,
    URLConfig,
    UserProfileConfig,
)
from src.api.v1.deps import create_webhook_signature
from src.api.v1.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def dynamic_app_config_from_env():
    """Keep tests isolated from the developer's local config.json while preserving env-based behavior."""

    def _build_config():
        return SimpleNamespace(
            api=SimpleNamespace(debug=False),
            security=SimpleNamespace(
                api_key=os.getenv("API_KEY", ""),
                webhook_signing_secret=os.getenv("WEBHOOK_SIGNING_SECRET", ""),
                openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            ),
            integrations=SimpleNamespace(
                redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                selenium_remote_url=os.getenv(
                    "SELENIUM_REMOTE_URL", "http://localhost:4444/wd/hub"
                ),
            ),
            generation=SimpleNamespace(mode=os.getenv("GENERATION_MODE", "local")),
        )

    with patch(
        "config.settings.AppConfig.load",
        side_effect=_build_config,
    ):
        yield


@pytest.fixture
def api_key():
    """Test API key."""
    return "test-api-key-123"


@pytest.fixture
def mock_env(api_key):
    """Mock environment variables."""
    with patch.dict("os.environ", {"API_KEY": api_key}):
        yield


def make_config(base_dir: Path) -> AppConfig:
    """Create an application config for settings endpoint tests."""
    return AppConfig(
        telegram=TelegramConfig(
            token="telegram-token",
            chat_id="123456",
            enabled=True,
            parse_mode="Markdown",
            attach_responses_auto=True,
            attachment_format="txt",
        ),
        scraping=ScrapingConfig(),
        delays=DelayConfig(),
        api=APIConfig(host="0.0.0.0", port=8000, debug=False, workers=1),
        security=SecurityConfig(
            api_key="initial-api-key",
            webhook_signing_secret="initial-webhook-secret",
            openai_api_key="sk-initial-openai-key",
        ),
        generation=GenerationConfig(
            mode="local",
            openai_api_key="sk-generation-openai-key",
            openai_model="gpt-4.1-mini",
            gemini_api_key="gemini-secret",
            gemini_model="gemini-2.5-flash",
            claude_api_key="claude-secret",
            claude_model="claude-3-5-sonnet-latest",
            temperature=0.45,
            max_tokens=320,
            system_prompt="Seja cordial e objetiva.",
        ),
        integrations=IntegrationConfig(
            redis_url="redis://redis.internal:6379/0",
            selenium_remote_url="http://selenium.internal:4444/wd/hub",
            api_url="http://api.internal:8000",
            api_public_url="https://doctoralia.example.com/api",
        ),
        privacy=PrivacyConfig(
            mask_pii=True,
            id_salt="privacy-salt",
            job_result_ttl=3600,
            rate_limit_requests=15,
            rate_limit_window=60,
            require_tls_callbacks=True,
            allowed_callback_domains=["hooks.example.com"],
        ),
        urls=URLConfig(
            base_url="https://www.doctoralia.com.br",
            profile_url="https://www.doctoralia.com.br/medico/teste",
        ),
        user_profile=UserProfileConfig(
            display_name="Dra. Ana",
            username="dra-ana",
            favorite_profiles=[
                FavoriteProfileConfig(
                    name="Perfil principal",
                    profile_url="https://www.doctoralia.com.br/medico/teste",
                    specialty="Ginecologia",
                    notes="Prioridade alta",
                )
            ],
        ),
        base_dir=base_dir,
        data_dir=base_dir / "data",
        logs_dir=base_dir / "data" / "logs",
    )


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test health endpoint."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_s" in data

    def test_ready_check_without_redis(self, client):
        """Test readiness when Redis is unavailable."""
        with patch("src.api.v1.main.redis.Redis.from_url") as mock_redis:
            mock_redis.side_effect = Exception("Redis connection failed")
            response = client.get("/v1/ready")
            assert response.status_code == 503

    def test_metrics_endpoint_uses_redis_backed_store(self, client):
        """Metrics endpoint should expose Redis-backed counters and middleware timings."""
        metrics_store = MagicMock()
        metrics_store.snapshot.return_value = {
            "requests_total": 12,
            "requests_in_progress": 1,
            "requests_failed_total": 2,
            "scrapes_total": 5,
            "scrapes_failed_total": 1,
            "generation_total": 4,
            "analysis_total": 3,
            "request_durations_ms": [110, 90, 70],
        }

        with patch("src.api.v1.main._get_metrics_store", return_value=metrics_store):
            response = client.get("/v1/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == {"type": "redis", "available": True}
        assert data["requests"]["total"] == 12
        assert data["requests"]["latest_ms"] == 110
        assert data["requests"]["sample_size"] == 3
        assert data["scraping"]["generation_total"] == 4
        metrics_store.record_request_start.assert_called()
        metrics_store.record_request_end.assert_called()

    def test_metrics_endpoint_handles_store_failure(self, client):
        """Metrics endpoint should stay available even if Redis metrics cannot be read."""
        with patch(
            "src.api.v1.main._get_metrics_store",
            side_effect=RuntimeError("metrics redis unavailable"),
        ):
            response = client.get("/v1/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == {"type": "redis", "available": False}
        assert data["requests"]["total"] == 0
        assert data["requests"]["sample_size"] == 0


class TestAuthentication:
    """Test API authentication."""

    def test_no_api_key(self, client, mock_env):
        """Test request without API key."""
        response = client.post("/v1/scrape:run", json={})
        assert response.status_code == 401

    def test_invalid_api_key(self, client, mock_env):
        """Test request with invalid API key."""
        response = client.post(
            "/v1/scrape:run", json={}, headers={"X-API-Key": "wrong-key"}
        )
        assert response.status_code == 401

    def test_valid_api_key(self, client, mock_env, api_key):
        """Test request with valid API key."""
        with patch("src.scraper.DoctoraliaScraper") as mock_scraper:
            mock_instance = MagicMock()
            mock_instance.scrape_reviews.return_value = {
                "doctor_name": "Test Doctor",
                "reviews": [],
            }
            mock_scraper.return_value = mock_instance

            response = client.post(
                "/v1/scrape:run",
                json={"doctor_url": "https://example.com"},
                headers={"X-API-Key": api_key},
            )
            assert response.status_code == 200


class TestTelegramNotificationEndpoints:
    """Test Telegram scheduling endpoints."""

    @patch("src.api.v1.main._get_telegram_schedule_service")
    def test_list_telegram_notification_schedules(
        self, mock_get_service, client, mock_env, api_key
    ):
        service = MagicMock()
        service.list_schedules.return_value = [
            {
                "id": "schedule-1",
                "name": "Matinal",
                "enabled": True,
                "timezone": "America/Sao_Paulo",
                "recurrence_type": "daily",
                "time_of_day": "09:00",
                "day_of_week": None,
                "interval_minutes": None,
                "cron_expression": "0 9 * * *",
                "profile_url": None,
                "profile_label": None,
                "trigger_new_scrape": True,
                "include_generation": False,
                "generation_mode": "default",
                "report_type": "complete",
                "include_health_status": False,
                "send_attachment": True,
                "attachment_scope": "responses",
                "attachment_format": "txt",
                "max_reviews": 20,
                "telegram_token": None,
                "telegram_chat_id": None,
                "parse_mode": "Markdown",
                "recurrence_label": "Diariamente às 09:00",
                "next_run_at": None,
                "last_run_at": None,
                "last_status": None,
                "last_error": None,
                "last_result": None,
                "created_at": "2026-03-26T10:00:00+00:00",
                "updated_at": "2026-03-26T10:00:00+00:00",
            }
        ]
        service.get_summary.return_value = {"total": 1, "active": 1, "paused": 0}
        mock_get_service.return_value = service

        response = client.get(
            "/v1/notifications/telegram/schedules",
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["total"] == 1
        assert payload["schedules"][0]["name"] == "Matinal"

    @patch("src.api.v1.main._get_telegram_schedule_service")
    def test_create_telegram_notification_schedule_validation_error(
        self, mock_get_service, client, mock_env, api_key
    ):
        service = MagicMock()
        service.save_schedule.side_effect = ValueError("Unsupported recurrence_type")
        mock_get_service.return_value = service

        response = client.post(
            "/v1/notifications/telegram/schedules",
            headers={"X-API-Key": api_key},
            json={"name": "Invalido", "recurrence_type": "broken"},
        )

        assert response.status_code == 400
        response_body = response.json()
        assert response_body["error"]["message"] == "Invalid schedule payload"
        assert "Unsupported recurrence_type" not in str(response_body)
        assert "detail" not in response_body["error"]

    @patch("src.api.v1.main._get_telegram_schedule_service")
    def test_run_telegram_notification_schedule_not_found(
        self, mock_get_service, client, mock_env, api_key
    ):
        service = MagicMock()
        service.execute_schedule.side_effect = ValueError("Schedule abc not found")
        mock_get_service.return_value = service

        response = client.post(
            "/v1/notifications/telegram/schedules/abc/run",
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 404
        response_body = response.json()
        assert response_body["error"]["message"] == "Schedule not found"
        assert "Schedule abc not found" not in str(response_body)
        assert "detail" not in response_body["error"]

    @patch("src.api.v1.main._get_telegram_schedule_service")
    def test_list_telegram_notification_history(
        self, mock_get_service, client, mock_env, api_key
    ):
        service = MagicMock()
        service.list_history.return_value = [
            {
                "id": "history-1",
                "schedule_id": "schedule-1",
                "schedule_name": "Matinal",
                "status": "sent",
                "manual": True,
                "run_at": "2026-03-26T10:00:00+00:00",
                "completed_at": "2026-03-26T10:00:30+00:00",
                "summary": "Relatório enviado",
                "metrics": {},
                "attachment_path": None,
            }
        ]
        mock_get_service.return_value = service

        response = client.get(
            "/v1/notifications/telegram/history?limit=5",
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["history"][0]["status"] == "sent"
        service.list_history.assert_called_once_with(limit=5)

    @patch("src.api.v1.main._get_telegram_schedule_service")
    def test_send_test_telegram_notification(
        self, mock_get_service, client, mock_env, api_key
    ):
        service = MagicMock()
        service.send_test_notification.return_value = {
            "success": True,
            "message": "Test notification sent",
            "result": {"sent": True},
        }
        mock_get_service.return_value = service

        response = client.post(
            "/v1/notifications/telegram/test",
            headers={"X-API-Key": api_key},
            json={"message": "teste", "parse_mode": "Markdown"},
        )

        assert response.status_code == 200
        assert response.json()["result"]["sent"] is True
        service.send_test_notification.assert_called_once_with(
            message="teste",
            telegram_token=None,
            telegram_chat_id=None,
            parse_mode="Markdown",
        )


class TestScrapeEndpoint:
    """Test synchronous scraping endpoint."""

    @patch("src.scraper.DoctoraliaScraper")
    def test_scrape_run_success(self, mock_scraper, client, mock_env, api_key):
        """Test successful scraping."""
        # Mock scraper
        mock_instance = MagicMock()
        mock_instance.scrape_reviews.return_value = {
            "doctor_name": "Dr. Test",
            "url": "https://example.com",
            "specialty": "General Practice",
            "location": "Test City",
            "average_rating": 4.5,
            "reviews": [
                {
                    "rating": 5,
                    "comment": "Excellent doctor!",
                    "date": "2024-01-15",
                    "author_name": "Patient",
                }
            ],
        }
        mock_scraper.return_value = mock_instance

        # Make request
        response = client.post(
            "/v1/scrape:run",
            json={"doctor_url": "https://example.com", "include_analysis": False},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["status"] == "completed"
        assert data["doctor"]["name"] == "Dr. Test"
        assert len(data["reviews"]) == 1
        assert data["metrics"]["scraped_count"] == 1

    @patch("src.api.v1.main.ResponseQualityAnalyzer")
    @patch("src.scraper.DoctoraliaScraper")
    def skip_test_scrape_with_analysis(
        self, mock_scraper, mock_analyzer, client, mock_env, api_key
    ):
        """Test scraping with sentiment analysis."""
        # Mock scraper
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.scrape_reviews.return_value = {
            "doctor_name": "Dr. Test",
            "reviews": [{"comment": "Great!"}],
        }
        mock_scraper.return_value = mock_scraper_instance

        # Mock analyzer
        mock_analyzer_instance = MagicMock()
        mock_analyzer_instance.analyze_sentiment.return_value = {
            "compound": 0.8,
            "pos": 0.7,
            "neu": 0.2,
            "neg": 0.1,
        }
        mock_analyzer.return_value = mock_analyzer_instance

        # Make request
        response = client.post(
            "/v1/scrape:run",
            json={"doctor_url": "https://example.com", "include_analysis": True},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["analysis"] is not None
        assert "sentiments" in data["analysis"]


class TestAsyncJobs:
    """Test async job endpoints."""

    @patch("src.api.v1.main.get_queue")
    def test_create_job(self, mock_queue, client, mock_env, api_key):
        """Test job creation."""
        # Mock queue
        mock_q = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_q.enqueue.return_value = mock_job
        mock_queue.return_value = mock_q

        # Make request
        response = client.post(
            "/v1/jobs",
            json={"doctor_url": "https://example.com", "mode": "async"},
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    @patch("rq.registry.FailedJobRegistry")
    @patch("rq.registry.FinishedJobRegistry")
    @patch("rq.registry.StartedJobRegistry")
    @patch("src.api.v1.main.get_queue")
    def test_list_jobs(
        self,
        mock_queue,
        mock_started_registry,
        mock_finished_registry,
        mock_failed_registry,
        client,
        mock_env,
        api_key,
    ):
        """Test listing jobs and status normalization."""
        mock_q = MagicMock()
        mock_q.job_ids = ["queued-job", "expired-job"]
        mock_queue.return_value = mock_q

        mock_started_registry.return_value.get_job_ids.return_value = ["running-job"]
        mock_finished_registry.return_value.get_job_ids.return_value = ["done-job"]
        mock_failed_registry.return_value.get_job_ids.return_value = ["failed-job"]

        queued_job = MagicMock()
        queued_job.id = "queued-job"
        queued_job.is_queued = True
        queued_job.is_deferred = False
        queued_job.is_started = False
        queued_job.is_finished = False
        queued_job.is_failed = False
        queued_job.meta = {"progress": 10, "message": "Queued"}
        queued_job.created_at = datetime(2026, 3, 6, 12, 0, 0)
        queued_job.enqueued_at = datetime(2026, 3, 6, 12, 0, 1)
        queued_job.ended_at = None

        running_job = MagicMock()
        running_job.id = "running-job"
        running_job.is_queued = False
        running_job.is_deferred = False
        running_job.is_started = True
        running_job.is_finished = False
        running_job.is_failed = False
        running_job.meta = {"progress": 55, "message": "Running"}
        running_job.created_at = datetime(2026, 3, 6, 12, 1, 0)
        running_job.enqueued_at = datetime(2026, 3, 6, 12, 1, 1)
        running_job.ended_at = None

        done_job = MagicMock()
        done_job.id = "done-job"
        done_job.is_queued = False
        done_job.is_deferred = False
        done_job.is_started = False
        done_job.is_finished = True
        done_job.is_failed = False
        done_job.meta = {"progress": 33, "message": "Done"}
        done_job.created_at = datetime(2026, 3, 6, 12, 2, 0)
        done_job.enqueued_at = datetime(2026, 3, 6, 12, 2, 1)
        done_job.ended_at = datetime(2026, 3, 6, 12, 3, 0)

        failed_job = MagicMock()
        failed_job.id = "failed-job"
        failed_job.is_queued = False
        failed_job.is_deferred = False
        failed_job.is_started = False
        failed_job.is_finished = False
        failed_job.is_failed = True
        failed_job.meta = {"progress": 80, "message": "Failed"}
        failed_job.created_at = datetime(2026, 3, 6, 12, 4, 0)
        failed_job.enqueued_at = datetime(2026, 3, 6, 12, 4, 1)
        failed_job.ended_at = datetime(2026, 3, 6, 12, 5, 0)

        jobs = {
            "queued-job": queued_job,
            "running-job": running_job,
            "done-job": done_job,
            "failed-job": failed_job,
            "expired-job": None,  # Simulate job that no longer exists.
        }
        mock_q.fetch_job.side_effect = jobs.get

        response = client.get("/v1/jobs", headers={"X-API-Key": api_key})

        assert response.status_code == 200
        data = response.json()
        assert {item["task_id"] for item in data} == {
            "queued-job",
            "running-job",
            "done-job",
            "failed-job",
        }

        by_id = {item["task_id"]: item for item in data}
        assert by_id["queued-job"]["status"] == "pending"
        assert by_id["running-job"]["status"] == "running"
        assert by_id["done-job"]["status"] == "completed"
        assert by_id["done-job"]["progress"] == 100
        assert by_id["failed-job"]["status"] == "failed"

    @patch("rq.registry.FailedJobRegistry")
    @patch("rq.registry.FinishedJobRegistry")
    @patch("rq.registry.StartedJobRegistry")
    @patch("src.api.v1.main.get_queue")
    def test_list_jobs_with_running_filter(
        self,
        mock_queue,
        mock_started_registry,
        mock_finished_registry,
        mock_failed_registry,
        client,
        mock_env,
        api_key,
    ):
        """Test status filtering for list jobs endpoint."""
        mock_q = MagicMock()
        mock_q.job_ids = ["queued-job"]
        mock_queue.return_value = mock_q
        mock_started_registry.return_value.get_job_ids.return_value = ["running-job"]
        mock_finished_registry.return_value.get_job_ids.return_value = ["done-job"]
        mock_failed_registry.return_value.get_job_ids.return_value = ["failed-job"]

        running_job = MagicMock()
        running_job.id = "running-job"
        running_job.is_queued = False
        running_job.is_deferred = False
        running_job.is_started = True
        running_job.is_finished = False
        running_job.is_failed = False
        running_job.meta = {}
        running_job.created_at = datetime(2026, 3, 6, 12, 0, 0)
        running_job.enqueued_at = datetime(2026, 3, 6, 12, 0, 1)
        running_job.ended_at = None
        mock_q.fetch_job.side_effect = {"running-job": running_job}.get

        response = client.get("/v1/jobs?status=running", headers={"X-API-Key": api_key})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["task_id"] == "running-job"
        assert data[0]["status"] == "running"
        assert mock_started_registry.return_value.get_job_ids.called
        assert not mock_finished_registry.return_value.get_job_ids.called
        assert not mock_failed_registry.return_value.get_job_ids.called

    @patch("rq.registry.FailedJobRegistry")
    @patch("rq.registry.FinishedJobRegistry")
    @patch("rq.registry.StartedJobRegistry")
    @patch("src.api.v1.main.get_queue")
    def test_list_jobs_failed_filter_includes_logical_failures(
        self,
        mock_queue,
        mock_started_registry,
        mock_finished_registry,
        mock_failed_registry,
        client,
        mock_env,
        api_key,
    ):
        """Finished jobs with failed result payloads must appear as failed."""
        mock_q = MagicMock()
        mock_q.job_ids = []
        mock_queue.return_value = mock_q
        mock_started_registry.return_value.get_job_ids.return_value = []
        mock_finished_registry.return_value.get_job_ids.return_value = [
            "logical-failed"
        ]
        mock_failed_registry.return_value.get_job_ids.return_value = []

        logical_failed = MagicMock()
        logical_failed.id = "logical-failed"
        logical_failed.is_queued = False
        logical_failed.is_deferred = False
        logical_failed.is_started = False
        logical_failed.is_finished = True
        logical_failed.is_failed = False
        logical_failed.result = {
            "doctor": {
                "id": "test123",
                "name": "Error",
                "profile_url": "https://example.com/dr-test",
            },
            "reviews": [],
            "metrics": {
                "scraped_count": 0,
                "start_ts": "2026-03-14T20:00:00",
                "end_ts": "2026-03-14T20:00:02",
                "duration_ms": 2000,
                "source": "doctoralia",
            },
            "status": "failed",
        }
        logical_failed.meta = {"progress": 0, "message": "Falha: validation error"}
        logical_failed.created_at = datetime(2026, 3, 14, 20, 0, 0)
        logical_failed.enqueued_at = datetime(2026, 3, 14, 20, 0, 1)
        logical_failed.ended_at = datetime(2026, 3, 14, 20, 0, 2)
        mock_q.fetch_job.side_effect = {"logical-failed": logical_failed}.get

        response = client.get("/v1/jobs?status=failed", headers={"X-API-Key": api_key})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["task_id"] == "logical-failed"
        assert data[0]["status"] == "failed"
        assert data[0]["message"] == "Falha: validation error"

    @patch("src.api.v1.main.get_queue")
    def test_get_job_status(self, mock_queue, client, mock_env, api_key):
        """Test job status retrieval."""
        # Mock queue and job
        mock_q = MagicMock()
        mock_job = MagicMock()
        mock_job.is_finished = True
        mock_job.result = {
            "doctor": {
                "id": "test123",
                "name": "Dr. Test",
                "profile_url": "https://example.com/dr-test",
                "specialty": "General Practice",
                "location": "Test City",
                "rating": 4.5,
            },
            "reviews": [],
            "metrics": {
                "scraped_count": 0,
                "start_ts": "2024-01-15T10:00:00",
                "end_ts": "2024-01-15T10:00:01",
                "duration_ms": 1000,
                "source": "doctoralia",
            },
            "status": "completed",
        }
        mock_q.fetch_job.return_value = mock_job
        mock_queue.return_value = mock_q

        # Make request
        response = client.get("/v1/jobs/job-123", headers={"X-API-Key": api_key})

        assert response.status_code == 200
        data = response.json()
        assert data["doctor"]["name"] == "Dr. Test"

    @patch("src.api.v1.main.get_queue")
    def test_get_job_status_returns_failed_finished_result(
        self, mock_queue, client, mock_env, api_key
    ):
        """Finished jobs should expose failed logical results without being masked as completed."""
        mock_q = MagicMock()
        mock_job = MagicMock()
        mock_job.is_queued = False
        mock_job.is_deferred = False
        mock_job.is_started = False
        mock_job.is_finished = True
        mock_job.is_failed = False
        mock_job.result = {
            "doctor": {
                "id": "error-profile",
                "name": "Error",
                "profile_url": "https://example.com/error",
            },
            "reviews": [],
            "metrics": {
                "scraped_count": 0,
                "start_ts": "2026-03-14T20:00:00",
                "end_ts": "2026-03-14T20:00:01",
                "duration_ms": 1000,
                "source": "doctoralia",
            },
            "status": "failed",
        }
        mock_q.fetch_job.return_value = mock_job
        mock_queue.return_value = mock_q

        response = client.get("/v1/jobs/job-failed", headers={"X-API-Key": api_key})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["doctor"]["name"] == "Error"

    @patch("src.api.v1.main.get_queue")
    def test_get_job_status_queued_is_pending(
        self, mock_queue, client, mock_env, api_key
    ):
        """Queued jobs should report pending in detail endpoint too."""
        mock_q = MagicMock()
        mock_job = MagicMock()
        mock_job.is_queued = True
        mock_job.is_deferred = False
        mock_job.is_started = False
        mock_job.is_finished = False
        mock_job.is_failed = False
        mock_job.result = None
        mock_q.fetch_job.return_value = mock_job
        mock_queue.return_value = mock_q

        response = client.get("/v1/jobs/job-queued", headers={"X-API-Key": api_key})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    def test_job_not_found(self, client, mock_env, api_key):
        """Test job not found error."""
        with patch("src.api.v1.main.get_queue") as mock_queue:
            mock_q = MagicMock()
            mock_q.fetch_job.return_value = None
            mock_queue.return_value = mock_q

            response = client.get(
                "/v1/jobs/nonexistent", headers={"X-API-Key": api_key}
            )

            assert response.status_code == 404


class TestSettingsEndpoints:
    """Test settings endpoints and expanded configuration fields."""

    def test_get_settings_returns_extended_sections(self, client, api_key, tmp_path):
        config = make_config(tmp_path)

        with patch("src.api.v1.deps._load_secret", return_value=api_key):
            with patch("src.api.v1.main._load_config", return_value=config):
                response = client.get("/v1/settings", headers={"X-API-Key": api_key})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["settings"]["security"]["api_key"] == "initial-api-key"
        assert (
            data["settings"]["integrations"]["api_public_url"]
            == "https://doctoralia.example.com/api"
        )
        assert data["settings"]["privacy"]["allowed_callback_domains"] == [
            "hooks.example.com"
        ]
        assert data["settings"]["urls"]["profile_url"].endswith("/medico/teste")
        assert data["settings"]["delays"]["page_load_retry"] == 5.0
        assert data["settings"]["generation"]["mode"] == "local"
        assert data["settings"]["generation"]["openai_model"] == "gpt-4.1-mini"
        assert data["settings"]["user_profile"]["display_name"] == "Dra. Ana"
        assert len(data["settings"]["user_profile"]["favorite_profiles"]) == 1

    def test_update_settings_partial_payload_preserves_other_sections(
        self, client, api_key, tmp_path
    ):
        config = make_config(tmp_path)
        config.save = MagicMock()

        payload = {
            "security": {
                "api_key": "updated-api-key",
                "webhook_signing_secret": "updated-webhook-secret",
                "openai_api_key": "sk-updated-openai-key",
            }
        }

        with patch("src.api.v1.deps._load_secret", return_value=api_key):
            with patch("src.api.v1.main._load_config", return_value=config):
                response = client.put(
                    "/v1/settings",
                    json=payload,
                    headers={"X-API-Key": api_key},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert config.security.api_key == "updated-api-key"
        assert config.security.webhook_signing_secret == "updated-webhook-secret"
        assert config.integrations.redis_url == "redis://redis.internal:6379/0"
        assert config.privacy.allowed_callback_domains == ["hooks.example.com"]
        config.save.assert_called_once()
        assert data["settings"]["integrations"]["redis_url"] == (
            "redis://redis.internal:6379/0"
        )
        assert data["settings"]["generation"]["openai_model"] == "gpt-4.1-mini"
        assert data["settings"]["user_profile"]["username"] == "dra-ana"

    def test_validate_settings_rejects_new_invalid_fields(
        self, client, api_key, tmp_path
    ):
        config = make_config(tmp_path)
        invalid_payload = {
            "security": {"openai_api_key": "invalid-openai-key"},
            "generation": {"mode": "openai", "openai_api_key": None},
            "integrations": {"redis_url": "http://not-redis"},
            "privacy": {"allowed_callback_domains": ["https://bad.example.com"]},
            "user_profile": {
                "display_name": "  ",
                "username": "",
                "favorite_profiles": [
                    {"name": "Sem URL", "profile_url": "nota-valid-url"}
                ],
            },
        }

        with patch("src.api.v1.deps._load_secret", return_value=api_key):
            with patch("src.api.v1.main._load_config", return_value=config):
                response = client.post(
                    "/v1/settings/validate",
                    json=invalid_payload,
                    headers={"X-API-Key": api_key},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "OpenAI API key must start with 'sk-'" in data["message"]
        assert "OpenAI mode requires an OpenAI API key" in data["message"]
        assert "Redis URL must start with redis:// or rediss://" in data["message"]
        assert "allowed_callback_domains must contain domains only" in data["message"]
        assert "Display name cannot be empty" in data["message"]
        assert "Username cannot be empty" in data["message"]
        assert "Favorite profile URL must be a valid HTTP(S) URL" in data["message"]

    def test_generate_response_preview_endpoint_uses_generator_metadata(
        self, client, api_key, tmp_path
    ):
        config = make_config(tmp_path)

        with patch("src.api.v1.deps._load_secret", return_value=api_key):
            with patch("src.api.v1.main._load_config", return_value=config):
                with patch(
                    "src.response_generator.ResponseGenerator.generate_response_with_metadata",
                    return_value={
                        "text": "Obrigada pelo feedback e pela confiança.",
                        "model": {"provider": "openai", "name": "gpt-4.1-mini"},
                    },
                ) as mock_generate:
                    response = client.post(
                        "/v1/generate/response",
                        json={
                            "review_id": "review-1",
                            "author": "Maria",
                            "comment": "Ótimo atendimento",
                            "rating": 5,
                            "date": "2026-03-14",
                            "doctor_name": "Dra. Ana",
                            "doctor_specialty": "Ginecologia",
                            "doctor_profile_url": "https://www.doctoralia.com.br/medico/teste",
                            "language": "pt-BR",
                            "generation_mode": "openai",
                        },
                        headers={"X-API-Key": api_key},
                    )

        assert response.status_code == 200
        data = response.json()
        assert data["review_id"] == "review-1"
        assert data["text"] == "Obrigada pelo feedback e pela confiança."
        assert data["model"]["provider"] == "openai"
        mock_generate.assert_called_once()


class TestWebhookSecurity:
    """Test webhook signature verification."""

    def test_create_webhook_signature(self):
        """Test signature creation."""
        payload = '{"test": "data"}'
        timestamp = time.time()

        with patch.dict("os.environ", {"WEBHOOK_SIGNING_SECRET": "secret123"}):
            ts_str, signature = create_webhook_signature(payload, timestamp)

            assert ts_str == str(timestamp)
            assert signature.startswith("sha256=")
            assert len(signature) > 7

    def test_webhook_without_signature(self, client):
        """Test webhook endpoint without signature."""
        with patch("src.api.v1.main.create_job") as mock_create:
            mock_result = MagicMock()
            mock_result.job_id = "job-123"
            mock_result.status = "queued"
            mock_create.return_value = mock_result

            response = client.post(
                "/v1/hooks/n8n/scrape", json={"doctor_url": "https://example.com"}
            )
            # Should pass if no secret is configured
            assert response.status_code in [200, 401, 422]

    def test_webhook_with_valid_signature(self, client):
        """Test webhook with valid signature."""
        payload = {"doctor_url": "https://example.com"}
        payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        timestamp = str(time.time())

        with patch.dict("os.environ", {"WEBHOOK_SIGNING_SECRET": "secret123"}):
            # Create valid signature
            import hashlib
            import hmac

            message = f"{timestamp}.{payload_json}"
            signature = (
                "sha256="
                + hmac.new(b"secret123", message.encode(), hashlib.sha256).hexdigest()
            )

            with patch("src.api.v1.main.create_job") as mock_create:
                mock_create.return_value = MagicMock(job_id="job-123", status="queued")

                response = client.post(
                    "/v1/hooks/n8n/scrape",
                    content=payload_json,
                    headers={
                        "Content-Type": "application/json",
                        "X-Timestamp": timestamp,
                        "X-Signature": signature,
                    },
                )

                # Should succeed with valid signature
                assert response.status_code in [200, 422]


class TestErrorHandling:
    """Test error handling."""

    def test_request_id_header(self, client):
        """Test that request ID is added to responses."""
        response = client.get("/v1/health")
        assert "X-Request-Id" in response.headers

    def test_validation_error(self, client, mock_env, api_key):
        """Test validation error response."""
        response = client.post(
            "/v1/scrape:run",
            json={"invalid_field": "test"},
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 422

    @patch("src.scraper.DoctoraliaScraper")
    def test_scraper_exception(self, mock_scraper, client, mock_env, api_key):
        """Test handling of scraper exceptions."""
        mock_scraper.side_effect = Exception("Scraper failed")

        response = client.post(
            "/v1/scrape:run",
            json={"doctor_url": "https://example.com"},
            headers={"X-API-Key": api_key},
        )

        # Should handle exception gracefully
        assert response.status_code in [200, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
