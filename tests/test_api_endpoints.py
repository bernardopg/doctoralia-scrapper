"""
Tests for API v1 endpoints not covered by tests/n8n/test_api.py.

Covers: scrape:run, jobs, generate/response, analyze/quality,
        settings, auth (extended), statistics, webhooks, version, root.
"""

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.v1.main import app
from src.config.settings import (
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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def dynamic_app_config_from_env():
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

    with (
        patch.dict("os.environ", {"DISABLE_NOTIFICATION_SCHEDULER": "true"}),
        patch(
            "src.config.settings.AppConfig.load",
            side_effect=_build_config,
        ),
    ):
        yield


@pytest.fixture
def api_key():
    return "test-api-key-123"


@pytest.fixture
def mock_env(api_key):
    with patch.dict("os.environ", {"API_KEY": api_key}):
        yield


def _make_full_config(base_dir: Path) -> AppConfig:
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
            api_key="test-api-key-123",
            webhook_signing_secret="test-webhook-secret",
            openai_api_key="sk-test-openai-key",
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
            system_prompt="Seja cordial.",
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


# ---------------------------------------------------------------------------
# Root & Version
# ---------------------------------------------------------------------------


class TestMiscEndpoints:
    def test_root_returns_docs_link(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "docs" in data
        assert data["docs"] == "/docs"

    def test_version_endpoint(self, client):
        response = client.get("/v1/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "start_time" in data


# ---------------------------------------------------------------------------
# Scrape
# ---------------------------------------------------------------------------


class TestScrapeEndpoints:
    def test_scrape_run_without_api_key_returns_401(self, client, mock_env):
        response = client.post(
            "/v1/scrape:run",
            json={"doctor_url": "https://www.doctoralia.com.br/medico/teste"},
        )
        assert response.status_code == 401

    def test_scrape_run_invalid_url_returns_422(self, client, mock_env, api_key):
        response = client.post(
            "/v1/scrape:run",
            json={"doctor_url": "not-a-url"},
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 422

    def test_scrape_run_success(self, client, mock_env, api_key, tmp_path):
        config = _make_full_config(tmp_path)

        mock_scraper_instance = MagicMock()
        mock_scraper_instance.scrape_reviews.return_value = {
            "doctor_name": "Dr. Teste",
            "reviews": [
                {
                    "id": "r1",
                    "author": "Paciente",
                    "comment": "Ótimo atendimento",
                    "rating": 5,
                    "date": "2026-01-01",
                }
            ],
            "average_rating": 4.8,
            "specialty": "Cardiologia",
            "url": "https://www.doctoralia.com.br/medico/teste",
        }

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch(
                "src.scraper.DoctoraliaScraper",
                return_value=mock_scraper_instance,
            ),
        ):
            response = client.post(
                "/v1/scrape:run",
                json={
                    "doctor_url": "https://www.doctoralia.com.br/medico/teste",
                    "include_analysis": False,
                    "include_generation": False,
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["doctor"]["name"] == "Dr. Teste"

    def test_scrape_run_scraper_error_returns_failed(
        self, client, mock_env, api_key, tmp_path
    ):
        config = _make_full_config(tmp_path)

        mock_scraper_instance = MagicMock()
        mock_scraper_instance.scrape_reviews.side_effect = RuntimeError(
            "Selenium crash"
        )

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch(
                "src.scraper.DoctoraliaScraper",
                return_value=mock_scraper_instance,
            ),
        ):
            response = client.post(
                "/v1/scrape:run",
                json={
                    "doctor_url": "https://www.doctoralia.com.br/medico/teste",
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"

    def test_scrape_run_with_analysis(self, client, mock_env, api_key, tmp_path):
        config = _make_full_config(tmp_path)

        mock_scraper_instance = MagicMock()
        mock_scraper_instance.scrape_reviews.return_value = {
            "doctor_name": "Dr. Teste",
            "reviews": [
                {
                    "id": "r1",
                    "author": "Paciente",
                    "comment": "Ótimo médico, muito atencioso",
                    "rating": 5,
                    "date": "2026-01-01",
                }
            ],
            "average_rating": 4.8,
            "url": "https://www.doctoralia.com.br/medico/teste",
        }

        mock_analyzer = MagicMock()
        mock_analyzer.sia.polarity_scores.return_value = {
            "compound": 0.8,
            "pos": 0.6,
            "neu": 0.3,
            "neg": 0.1,
        }

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch(
                "src.scraper.DoctoraliaScraper",
                return_value=mock_scraper_instance,
            ),
            patch(
                "src.response_quality_analyzer.ResponseQualityAnalyzer",
                return_value=mock_analyzer,
            ),
        ):
            response = client.post(
                "/v1/scrape:run",
                json={
                    "doctor_url": "https://www.doctoralia.com.br/medico/teste",
                    "include_analysis": True,
                    "include_generation": False,
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["analysis"] is not None

    def test_scrape_run_with_generation(self, client, mock_env, api_key, tmp_path):
        config = _make_full_config(tmp_path)

        mock_scraper_instance = MagicMock()
        mock_scraper_instance.scrape_reviews.return_value = {
            "doctor_name": "Dr. Teste",
            "reviews": [
                {
                    "id": "r1",
                    "author": "Paciente",
                    "comment": "Bom médico",
                    "rating": 4,
                    "date": "2026-01-01",
                }
            ],
            "url": "https://www.doctoralia.com.br/medico/teste",
        }

        mock_generator = MagicMock()
        mock_generator.generate_response_with_metadata.return_value = {
            "text": "Obrigado pela avaliação!",
            "model": {"type": "template", "provider": "local", "mode": "local"},
        }

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch(
                "src.scraper.DoctoraliaScraper",
                return_value=mock_scraper_instance,
            ),
            patch(
                "src.response_generator.ResponseGenerator",
                return_value=mock_generator,
            ),
        ):
            response = client.post(
                "/v1/scrape:run",
                json={
                    "doctor_url": "https://www.doctoralia.com.br/medico/teste",
                    "include_analysis": False,
                    "include_generation": True,
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["generation"] is not None
        assert len(data["generation"]["responses"]) == 1


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


class TestJobEndpoints:
    @patch("src.jobs.queue.get_queue")
    def test_create_job_success(
        self, mock_get_queue, client, mock_env, api_key, tmp_path
    ):
        config = _make_full_config(tmp_path)
        queue = MagicMock()
        mock_get_queue.return_value = queue

        with patch("src.config.settings.AppConfig.load", return_value=config):
            response = client.post(
                "/v1/jobs",
                json={
                    "doctor_url": "https://www.doctoralia.com.br/medico/teste",
                    "mode": "async",
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        queue.enqueue.assert_called_once()

    @patch("src.jobs.queue.get_queue")
    def test_create_job_without_auth_returns_401(
        self, mock_get_queue, client, mock_env
    ):
        response = client.post(
            "/v1/jobs",
            json={
                "doctor_url": "https://www.doctoralia.com.br/medico/teste",
                "mode": "async",
            },
        )
        assert response.status_code == 401

    @patch("src.jobs.queue.get_queue")
    def test_create_job_with_idempotency_key_returns_existing(
        self, mock_get_queue, client, mock_env, api_key, tmp_path
    ):
        config = _make_full_config(tmp_path)
        mock_redis = MagicMock()
        mock_redis.get.return_value = b"existing-job-id-123"

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch(
                "src.api.v1.routers.jobs.redis.Redis.from_url", return_value=mock_redis
            ),
        ):
            response = client.post(
                "/v1/jobs",
                json={
                    "doctor_url": "https://www.doctoralia.com.br/medico/teste",
                    "mode": "async",
                    "idempotency_key": "unique-key-1",
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == "existing-job-id-123"
        assert data["message"] == "Job already exists"

    @patch("src.jobs.queue.get_queue")
    def test_get_job_status_found(self, mock_get_queue, client, mock_env, api_key):
        from src.integrations.n8n.normalize import make_unified_result

        unified = make_unified_result(
            doctor_data={"name": "Dr. Teste", "url": "https://example.com"},
            reviews_data=[],
            status="completed",
        )

        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.is_queued = False
        mock_job.is_deferred = False
        mock_job.is_started = False
        mock_job.is_finished = True
        mock_job.is_failed = False
        mock_job.result = unified

        queue = MagicMock()
        queue.fetch_job.return_value = mock_job
        mock_get_queue.return_value = queue

        response = client.get(
            "/v1/jobs/job-123",
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200

    @patch("src.jobs.queue.get_queue")
    def test_get_job_status_not_found(self, mock_get_queue, client, mock_env, api_key):
        queue = MagicMock()
        queue.fetch_job.return_value = None
        mock_get_queue.return_value = queue

        response = client.get(
            "/v1/jobs/nonexistent-job",
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 404

    @patch("src.jobs.queue.get_queue")
    def test_list_jobs(self, mock_get_queue, client, mock_env, api_key):
        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.is_queued = True
        mock_job.is_deferred = False
        mock_job.is_started = False
        mock_job.is_finished = False
        mock_job.is_failed = False
        mock_job.meta = {"progress": 0, "message": "Queued"}
        mock_job.created_at = None
        mock_job.enqueued_at = None
        mock_job.ended_at = None
        mock_job.result = None

        queue = MagicMock()
        queue.job_ids = ["job-1"]
        queue.fetch_job.return_value = mock_job
        mock_get_queue.return_value = queue

        with (
            patch("rq.registry.StartedJobRegistry") as mock_started,
            patch("rq.registry.FinishedJobRegistry") as mock_finished,
            patch("rq.registry.FailedJobRegistry") as mock_failed,
        ):
            mock_started.return_value.get_job_ids.return_value = []
            mock_finished.return_value.get_job_ids.return_value = []
            mock_failed.return_value.get_job_ids.return_value = []

            response = client.get(
                "/v1/jobs",
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["task_id"] == "job-1"
        assert data[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


class TestGenerationEndpoints:
    def test_generate_response_local_mode(self, client, mock_env, api_key, tmp_path):
        config = _make_full_config(tmp_path)

        mock_generator = MagicMock()
        mock_generator.generate_response_with_metadata.return_value = {
            "text": "Obrigada pelo feedback, Paciente!",
            "model": {"type": "template", "provider": "local", "mode": "local"},
        }

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch(
                "src.response_generator.ResponseGenerator",
                return_value=mock_generator,
            ),
        ):
            response = client.post(
                "/v1/generate/response",
                json={
                    "comment": "Ótimo atendimento!",
                    "author": "Paciente",
                    "rating": 5,
                    "doctor_name": "Dr. Teste",
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert data["text"] == "Obrigada pelo feedback, Paciente!"

    def test_generate_response_missing_comment_returns_422(
        self, client, mock_env, api_key
    ):
        response = client.post(
            "/v1/generate/response",
            json={"author": "Paciente"},
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 422

    def test_generate_response_generator_valueerror_returns_400(
        self, client, mock_env, api_key, tmp_path
    ):
        config = _make_full_config(tmp_path)

        mock_generator = MagicMock()
        mock_generator.generate_response_with_metadata.side_effect = ValueError(
            "API key não configurada"
        )

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch(
                "src.response_generator.ResponseGenerator",
                return_value=mock_generator,
            ),
        ):
            response = client.post(
                "/v1/generate/response",
                json={"comment": "Bom médico"},
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 400

    def test_generate_response_unexpected_error_returns_500(
        self, client, mock_env, api_key, tmp_path
    ):
        config = _make_full_config(tmp_path)

        mock_generator = MagicMock()
        mock_generator.generate_response_with_metadata.side_effect = RuntimeError(
            "Unexpected"
        )

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch(
                "src.response_generator.ResponseGenerator",
                return_value=mock_generator,
            ),
        ):
            response = client.post(
                "/v1/generate/response",
                json={"comment": "Bom médico"},
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 500

    def test_generate_response_without_auth_returns_401(self, client, mock_env):
        response = client.post(
            "/v1/generate/response",
            json={"comment": "Bom médico"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Quality Analysis
# ---------------------------------------------------------------------------


class TestQualityAnalysisEndpoints:
    def test_analyze_quality_success(self, client, mock_env, api_key):
        mock_analyzer = MagicMock()
        mock_score = MagicMock()
        mock_score.to_dict.return_value = {
            "overall_score": 75.0,
            "sentiment_score": 0.8,
            "length_score": 60.0,
            "empathy_score": 80.0,
            "clarity_score": 70.0,
            "professionalism_score": 90.0,
            "actionability_score": 50.0,
        }
        mock_analysis = MagicMock()
        mock_analysis.score = mock_score
        mock_analysis.strengths = ["Empática"]
        mock_analysis.weaknesses = ["Curta"]
        mock_analysis.suggestions = ["Expandir resposta"]
        mock_analysis.keywords = ["obrigado"]
        mock_analysis.sentiment = "positive"
        mock_analysis.readability_score = 65.0
        mock_analyzer.analyze_response.return_value = mock_analysis

        with patch(
            "src.response_quality_analyzer.ResponseQualityAnalyzer",
            return_value=mock_analyzer,
        ):
            response = client.post(
                "/v1/analyze/quality",
                json={
                    "response_text": "Obrigada pelo carinho, estou sempre disponível.",
                    "original_review": "Ótima médica!",
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["score"]["overall_score"] == 75.0
        assert data["sentiment"] == "positive"
        assert "Empática" in data["strengths"]

    def test_analyze_quality_batch(self, client, mock_env, api_key):
        mock_analyzer = MagicMock()
        mock_score = MagicMock()
        mock_score.to_dict.return_value = {
            "overall_score": 70.0,
            "sentiment_score": 0.5,
            "length_score": 50.0,
            "empathy_score": 60.0,
            "clarity_score": 70.0,
            "professionalism_score": 80.0,
            "actionability_score": 40.0,
        }
        mock_analysis = MagicMock()
        mock_analysis.score = mock_score
        mock_analysis.strengths = ["Profissional"]
        mock_analysis.weaknesses = []
        mock_analysis.suggestions = []
        mock_analysis.keywords = ["obrigado"]
        mock_analysis.sentiment = "positive"
        mock_analysis.readability_score = 60.0
        mock_analyzer.analyze_response.return_value = mock_analysis

        with patch(
            "src.response_quality_analyzer.ResponseQualityAnalyzer",
            return_value=mock_analyzer,
        ):
            response = client.post(
                "/v1/analyze/quality/batch",
                json={
                    "analyses": [
                        {
                            "response_text": "Obrigada!",
                            "original_review": "Boa médica",
                        },
                        {
                            "response_text": "Agradeço o feedback.",
                            "original_review": "Razoável",
                        },
                    ]
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_analyze_quality_without_auth_returns_401(self, client, mock_env):
        response = client.post(
            "/v1/analyze/quality",
            json={"response_text": "Obrigada!"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestSettingsEndpoints:
    def test_get_settings_returns_masked_secrets(
        self, client, mock_env, api_key, tmp_path
    ):
        config = _make_full_config(tmp_path)

        with patch("src.config.settings.AppConfig.load", return_value=config):
            response = client.get(
                "/v1/settings",
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        settings = data["settings"]
        assert settings["security"]["api_key"].startswith("********")
        assert settings["security"]["webhook_signing_secret"].startswith("********")
        assert settings["generation"]["openai_api_key"].startswith("********")
        assert settings["generation"]["gemini_api_key"].startswith("********")
        assert settings["generation"]["claude_api_key"].startswith("********")

    def test_get_settings_without_auth_returns_401(self, client, mock_env):
        response = client.get("/v1/settings")
        assert response.status_code == 401

    def test_update_settings_success(self, client, mock_env, api_key, tmp_path):
        config = _make_full_config(tmp_path)
        config.save = MagicMock()

        with patch("src.config.settings.AppConfig.load", return_value=config):
            response = client.put(
                "/v1/settings",
                json={
                    "telegram": {
                        "enabled": False,
                        "token": "********oken",
                        "chat_id": "123456",
                        "parse_mode": "Markdown",
                        "attach_responses_auto": True,
                        "attachment_format": "txt",
                    },
                    "scraping": {
                        "headless": True,
                        "timeout": 60,
                        "delay_min": 2.0,
                        "delay_max": 4.0,
                        "max_retries": 5,
                        "page_load_timeout": 45,
                        "implicit_wait": 20,
                        "explicit_wait": 30,
                    },
                    "delays": {
                        "human_like_min": 1.0,
                        "human_like_max": 3.0,
                        "retry_base": 2.0,
                        "error_recovery": 10.0,
                        "rate_limit_retry": 60.0,
                        "page_load_retry": 5.0,
                    },
                    "api": {
                        "host": "0.0.0.0",
                        "port": 8000,
                        "debug": False,
                        "workers": 1,
                    },
                    "security": {
                        "api_key": "********-123",
                        "webhook_signing_secret": "********cret",
                        "openai_api_key": "********-key",
                    },
                    "generation": {
                        "mode": "local",
                        "openai_api_key": "********-key",
                        "openai_model": "gpt-4.1-mini",
                        "gemini_api_key": "********cret",
                        "gemini_model": "gemini-2.5-flash",
                        "claude_api_key": "********cret",
                        "claude_model": "claude-3-5-sonnet-latest",
                        "temperature": 0.45,
                        "max_tokens": 320,
                        "system_prompt": "Seja cordial.",
                    },
                    "integrations": {
                        "redis_url": "redis://redis.internal:6379/0",
                        "selenium_remote_url": "http://selenium.internal:4444/wd/hub",
                        "api_url": "http://api.internal:8000",
                        "api_public_url": "https://doctoralia.example.com/api",
                    },
                    "privacy": {
                        "mask_pii": True,
                        "id_salt": "********salt",
                        "job_result_ttl": 3600,
                        "rate_limit_requests": 15,
                        "rate_limit_window": 60,
                        "require_tls_callbacks": True,
                        "allowed_callback_domains": ["hooks.example.com"],
                    },
                    "urls": {
                        "base_url": "https://www.doctoralia.com.br",
                        "profile_url": "https://www.doctoralia.com.br/medico/teste",
                    },
                    "user_profile": {
                        "display_name": "Dra. Ana",
                        "username": "dra-ana",
                        "favorite_profiles": [
                            {
                                "name": "Perfil principal",
                                "profile_url": "https://www.doctoralia.com.br/medico/teste",
                                "specialty": "Ginecologia",
                                "notes": "Prioridade alta",
                            }
                        ],
                    },
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        config.save.assert_called_once()

    def test_validate_settings_valid(self, client, mock_env, api_key, tmp_path):
        config = _make_full_config(tmp_path)

        with patch("src.config.settings.AppConfig.load", return_value=config):
            response = client.post(
                "/v1/settings/validate",
                json={
                    "telegram": {
                        "enabled": True,
                        "token": "123456789:ABCdefGHI_JKLmnoPQRstuVWXyz",
                        "chat_id": "123456",
                        "parse_mode": "Markdown",
                        "attach_responses_auto": True,
                        "attachment_format": "txt",
                    },
                    "scraping": {
                        "headless": True,
                        "timeout": 60,
                        "delay_min": 2.0,
                        "delay_max": 4.0,
                        "max_retries": 5,
                        "page_load_timeout": 45,
                        "implicit_wait": 20,
                        "explicit_wait": 30,
                    },
                    "delays": {
                        "human_like_min": 1.0,
                        "human_like_max": 3.0,
                        "retry_base": 2.0,
                        "error_recovery": 10.0,
                        "rate_limit_retry": 60.0,
                        "page_load_retry": 5.0,
                    },
                    "api": {
                        "host": "0.0.0.0",
                        "port": 8000,
                        "debug": False,
                        "workers": 1,
                    },
                    "security": {
                        "api_key": "test-api-key-123",
                        "webhook_signing_secret": "test-webhook-secret",
                        "openai_api_key": "sk-test-openai-key",
                    },
                    "generation": {
                        "mode": "local",
                        "openai_api_key": "sk-generation-openai-key",
                        "openai_model": "gpt-4.1-mini",
                        "gemini_api_key": "gemini-secret",
                        "gemini_model": "gemini-2.5-flash",
                        "claude_api_key": "claude-secret",
                        "claude_model": "claude-3-5-sonnet-latest",
                        "temperature": 0.45,
                        "max_tokens": 320,
                        "system_prompt": "Seja cordial.",
                    },
                    "integrations": {
                        "redis_url": "redis://redis.internal:6379/0",
                        "selenium_remote_url": "http://selenium.internal:4444/wd/hub",
                        "api_url": "http://api.internal:8000",
                        "api_public_url": "https://doctoralia.example.com/api",
                    },
                    "privacy": {
                        "mask_pii": True,
                        "id_salt": "privacy-salt",
                        "job_result_ttl": 3600,
                        "rate_limit_requests": 15,
                        "rate_limit_window": 60,
                        "require_tls_callbacks": True,
                        "allowed_callback_domains": ["hooks.example.com"],
                    },
                    "urls": {
                        "base_url": "https://www.doctoralia.com.br",
                        "profile_url": "https://www.doctoralia.com.br/medico/teste",
                    },
                    "user_profile": {
                        "display_name": "Dra. Ana",
                        "username": "dra-ana",
                        "favorite_profiles": [
                            {
                                "name": "Perfil principal",
                                "profile_url": "https://www.doctoralia.com.br/medico/teste",
                            }
                        ],
                    },
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Settings are valid"

    def test_validate_settings_invalid_returns_errors(
        self, client, mock_env, api_key, tmp_path
    ):
        config = _make_full_config(tmp_path)

        with patch("src.config.settings.AppConfig.load", return_value=config):
            response = client.post(
                "/v1/settings/validate",
                json={
                    "telegram": {
                        "enabled": False,
                        "parse_mode": "Markdown",
                        "attach_responses_auto": True,
                        "attachment_format": "txt",
                    },
                    "scraping": {
                        "headless": True,
                        "timeout": 60,
                        "delay_min": 5.0,
                        "delay_max": 2.0,
                        "max_retries": 5,
                        "page_load_timeout": 45,
                        "implicit_wait": 20,
                        "explicit_wait": 30,
                    },
                    "delays": {
                        "human_like_min": 1.0,
                        "human_like_max": 3.0,
                        "retry_base": 2.0,
                        "error_recovery": 10.0,
                        "rate_limit_retry": 60.0,
                        "page_load_retry": 5.0,
                    },
                    "api": {
                        "host": "0.0.0.0",
                        "port": 8000,
                        "debug": False,
                        "workers": 1,
                    },
                    "security": {
                        "api_key": "test-api-key-123",
                        "webhook_signing_secret": "test-webhook-secret",
                        "openai_api_key": "sk-test-openai-key",
                    },
                    "generation": {
                        "mode": "local",
                        "openai_api_key": "sk-generation-openai-key",
                        "openai_model": "gpt-4.1-mini",
                        "gemini_api_key": "gemini-secret",
                        "gemini_model": "gemini-2.5-flash",
                        "claude_api_key": "claude-secret",
                        "claude_model": "claude-3-5-sonnet-latest",
                        "temperature": 0.45,
                        "max_tokens": 320,
                        "system_prompt": "Seja cordial.",
                    },
                    "integrations": {
                        "redis_url": "redis://redis.internal:6379/0",
                        "selenium_remote_url": "http://selenium.internal:4444/wd/hub",
                    },
                    "privacy": {
                        "mask_pii": True,
                        "id_salt": "privacy-salt",
                        "job_result_ttl": 3600,
                        "rate_limit_requests": 15,
                        "rate_limit_window": 60,
                        "require_tls_callbacks": True,
                        "allowed_callback_domains": [],
                    },
                    "urls": {
                        "base_url": "https://www.doctoralia.com.br",
                    },
                    "user_profile": {
                        "display_name": "Dra. Ana",
                        "username": "dra-ana",
                        "favorite_profiles": [],
                    },
                },
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "delay_min" in data["message"]


# ---------------------------------------------------------------------------
# Auth (extended — basic auth covered in tests/n8n/test_api.py)
# ---------------------------------------------------------------------------


class TestAuthEndpoints:
    def test_auth_status_when_disabled(self, client, tmp_path):
        config = _make_full_config(tmp_path)
        config.security.api_key = ""

        with patch("src.config.settings.AppConfig.load", return_value=config):
            response = client.get("/v1/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_login_when_auth_disabled(self, client, tmp_path):
        config = _make_full_config(tmp_path)
        config.security.api_key = ""

        with patch("src.config.settings.AppConfig.load", return_value=config):
            response = client.post(
                "/v1/auth/login",
                json={"username": "admin", "password": "anything"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "disabled" in data["message"].lower()

    def test_change_password_requires_api_key(self, client, mock_env):
        response = client.post(
            "/v1/auth/change-password",
            json={
                "current_password": "old",
                "new_password": "NewPassword123",
            },
        )
        assert response.status_code == 401

    def test_change_password_rejects_short_password(
        self, client, mock_env, api_key, tmp_path
    ):
        config = _make_full_config(tmp_path)
        config.save = MagicMock()

        with patch("src.config.settings.AppConfig.load", return_value=config):
            response = client.post(
                "/v1/auth/change-password",
                headers={"X-API-Key": api_key},
                json={
                    "current_password": api_key,
                    "new_password": "short",
                },
            )

        assert response.status_code == 400

    def test_change_password_rejects_wrong_current(
        self, client, mock_env, api_key, tmp_path
    ):
        config = _make_full_config(tmp_path)

        with patch("src.config.settings.AppConfig.load", return_value=config):
            response = client.post(
                "/v1/auth/change-password",
                headers={"X-API-Key": api_key},
                json={
                    "current_password": "wrong-password",
                    "new_password": "NewPassword123",
                },
            )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class TestStatisticsEndpoint:
    def test_get_statistics_success(self, client, mock_env, api_key, tmp_path):
        config = _make_full_config(tmp_path)
        mock_stats = {
            "total_scraped_doctors": 5,
            "total_reviews": 120,
            "average_rating": 4.5,
            "last_scrape_time": "2026-05-10T10:00:00",
            "data_files": ["doctor1.json", "doctor2.json"],
            "platform_stats": {"doctoralia": {"doctors": 5, "reviews": 120}},
        }

        mock_service = MagicMock()
        mock_service.get_scraper_stats.return_value = mock_stats

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch("src.services.stats.StatsService", return_value=mock_service),
        ):
            response = client.get(
                "/v1/statistics",
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_scraped_doctors"] == 5
        assert data["total_reviews"] == 120
        assert data["average_rating"] == 4.5

    def test_get_statistics_without_auth_returns_401(self, client, mock_env):
        response = client.get("/v1/statistics")
        assert response.status_code == 401

    def test_get_statistics_empty_data(self, client, mock_env, api_key, tmp_path):
        config = _make_full_config(tmp_path)
        mock_stats = {
            "total_scraped_doctors": 0,
            "total_reviews": 0,
            "average_rating": 0.0,
            "last_scrape_time": None,
            "data_files": [],
            "platform_stats": {},
        }

        mock_service = MagicMock()
        mock_service.get_scraper_stats.return_value = mock_stats

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch("src.services.stats.StatsService", return_value=mock_service),
        ):
            response = client.get(
                "/v1/statistics",
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_scraped_doctors"] == 0
        assert data["total_reviews"] == 0


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


class TestWebhookEndpoint:
    @patch("src.jobs.queue.get_queue")
    def test_webhook_scrape_without_secret_succeeds(
        self, mock_get_queue, client, tmp_path
    ):
        config = _make_full_config(tmp_path)
        config.security.webhook_signing_secret = ""
        queue = MagicMock()
        mock_get_queue.return_value = queue

        def _fake_load_secret(field, env_name):
            if field == "webhook_signing_secret":
                return ""
            if field == "api_key":
                return ""
            return None

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch("src.api.v1.deps._load_secret", side_effect=_fake_load_secret),
        ):
            response = client.post(
                "/v1/hooks/n8n/scrape",
                json={
                    "doctor_url": "https://www.doctoralia.com.br/medico/teste",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["received"] is True
        assert "job_id" in data

    def test_webhook_scrape_missing_signature_returns_401(
        self, client, mock_env, tmp_path
    ):
        config = _make_full_config(tmp_path)

        with (
            patch("src.config.settings.AppConfig.load", return_value=config),
            patch.dict(
                "os.environ",
                {"WEBHOOK_SIGNING_SECRET": "test-webhook-secret"},
            ),
        ):
            response = client.post(
                "/v1/hooks/n8n/scrape",
                json={
                    "doctor_url": "https://www.doctoralia.com.br/medico/teste",
                },
            )

        assert response.status_code == 401

    @patch("src.jobs.queue.get_queue")
    def test_webhook_scrape_valid_signature(self, mock_get_queue, client, tmp_path):
        config = _make_full_config(tmp_path)
        queue = MagicMock()
        mock_get_queue.return_value = queue

        import hashlib
        import hmac

        body = json.dumps({"doctor_url": "https://www.doctoralia.com.br/medico/teste"})
        timestamp = str(time.time())
        secret = "test-webhook-secret"
        message = f"{timestamp}.{body}"
        signature = hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        with patch("src.config.settings.AppConfig.load", return_value=config):
            response = client.post(
                "/v1/hooks/n8n/scrape",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Timestamp": timestamp,
                    "X-Signature": f"sha256={signature}",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["received"] is True


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_general_exception_returns_500_with_request_id(self, client, mock_env):
        response = client.get("/v1/nonexistent-endpoint")
        assert response.status_code in (404, 405)

    def test_http_exception_returns_consistent_schema(self, client, mock_env, api_key):
        with patch("src.jobs.queue.get_queue") as mock_queue:
            mock_queue.return_value.fetch_job.return_value = None
            response = client.get(
                "/v1/jobs/not-real",
                headers={"X-API-Key": api_key},
            )

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert data["error"]["code"] == "NOT_FOUND"
