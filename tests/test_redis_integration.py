import os
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import SplitResult, urlsplit, urlunsplit

import pytest
import redis

from src.api.v1.metrics_store import RedisAPIMetricsStore
from src.integrations.n8n import privacy
from src.jobs.queue import get_queue, get_redis_connection


def redis_echo(value: str) -> str:
    """Simple callable used to enqueue a real RQ job in Redis."""
    return value


def _build_test_redis_url(base_url: str) -> str:
    parsed = urlsplit(base_url or "redis://localhost:6379/0")
    normalized = SplitResult(
        scheme=parsed.scheme or "redis",
        netloc=parsed.netloc or "localhost:6379",
        path="/15",
        query=parsed.query,
        fragment=parsed.fragment,
    )
    return urlunsplit(normalized)


@pytest.fixture
def real_redis_url() -> str:
    return _build_test_redis_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


@pytest.fixture
def real_redis_client(real_redis_url: str):
    client = redis.Redis.from_url(real_redis_url)
    try:
        client.ping()
    except redis.RedisError as exc:
        pytest.skip(f"Redis real indisponivel para testes de integracao: {exc}")

    client.flushdb()
    yield client
    client.flushdb()
    client.close()


def test_get_redis_connection_uses_real_redis(real_redis_client, real_redis_url: str):
    config = SimpleNamespace(integrations=SimpleNamespace(redis_url=real_redis_url))

    with patch("config.settings.AppConfig.load", return_value=config):
        connection = get_redis_connection()

    assert connection.ping() is True
    connection.close()


def test_get_queue_enqueues_job_in_real_redis(real_redis_client, real_redis_url: str):
    config = SimpleNamespace(integrations=SimpleNamespace(redis_url=real_redis_url))

    with patch("config.settings.AppConfig.load", return_value=config):
        queue = get_queue("doctoralia-integration")
        job = queue.enqueue(redis_echo, "ok-from-redis")

    assert queue.name == "doctoralia-integration"
    assert job.timeout == 1800
    assert queue.job_ids == [job.id]
    assert real_redis_client.exists(f"rq:job:{job.id}") == 1


def test_apply_data_retention_sets_ttl_on_real_redis(real_redis_client):
    job_id = "job-real-ttl"
    keys = [
        f"rq:job:{job_id}",
        f"rq:job:{job_id}:result",
        f"job:metadata:{job_id}",
    ]
    for key in keys:
        real_redis_client.set(key, "payload")

    privacy.apply_data_retention(real_redis_client, job_id, ttl=30)

    for key in keys:
        ttl = real_redis_client.ttl(key)
        assert 0 < ttl <= 30


def test_rate_limiter_uses_real_redis_state(real_redis_client):
    limiter = privacy.RateLimiter(real_redis_client, max_requests=2, window=60)

    assert limiter.is_allowed("integration-client") is True
    assert limiter.get_remaining("integration-client") == 1
    assert limiter.is_allowed("integration-client") is True
    assert limiter.get_remaining("integration-client") == 0
    assert limiter.is_allowed("integration-client") is False


def test_mask_pii_and_sanitize_review():
    review = {
        "author_name": "Maria Silva",
        "comment": "Contato: maria@example.com e +55 11 99999-1234",
        "text": "CPF 123.456.789-10",
    }

    sanitized = privacy.sanitize_review(review)

    assert sanitized["author_name"] == "Maria ***"
    assert "***@***.***" in sanitized["comment"]
    assert "***-****" in sanitized["comment"]
    assert "***.***.***-**" in sanitized["text"]


def test_validate_callback_url_respects_tls_and_allowed_domains(monkeypatch):
    monkeypatch.setattr(
        privacy,
        "_load_privacy_config",
        lambda: SimpleNamespace(
            mask_pii=True,
            require_tls_callbacks=True,
            id_salt="privacy-salt",
            job_result_ttl=3600,
            rate_limit_requests=10,
            rate_limit_window=60,
            allowed_callback_domains=["hooks.example.com"],
        ),
    )

    assert privacy.validate_callback_url("https://hooks.example.com/webhook") is True
    assert privacy.validate_callback_url("http://localhost:5678/webhook") is True
    assert privacy.validate_callback_url("https://evil.example.com/webhook") is False
    assert privacy.validate_callback_url("http://evil.example.com/webhook") is False


def test_api_metrics_store_records_and_reads_metrics_with_real_redis(
    real_redis_client,
):
    store = RedisAPIMetricsStore(
        real_redis_client,
        prefix="doctoralia:test:metrics",
        max_samples=5,
        active_request_ttl_s=60,
    )

    store.record_request_start("req-1", started_at_s=100.0)
    store.increment_scrapes()
    store.increment_analysis()
    active_snapshot = store.snapshot(now_s=100.0)

    assert active_snapshot["requests_total"] == 1
    assert active_snapshot["requests_in_progress"] == 1
    assert active_snapshot["scrapes_total"] == 1
    assert active_snapshot["analysis_total"] == 1

    store.record_request_end("req-1", duration_ms=125, failed=True)
    store.increment_generation(2)
    final_snapshot = store.snapshot(now_s=101.0)

    assert final_snapshot["requests_in_progress"] == 0
    assert final_snapshot["requests_failed_total"] == 1
    assert final_snapshot["generation_total"] == 2
    assert final_snapshot["request_durations_ms"] == [125]


def test_api_metrics_store_trims_duration_samples(real_redis_client):
    store = RedisAPIMetricsStore(
        real_redis_client,
        prefix="doctoralia:test:metrics:trim",
        max_samples=3,
        active_request_ttl_s=60,
    )

    for idx, duration in enumerate([10, 20, 30, 40], start=1):
        request_id = f"req-{idx}"
        store.record_request_start(request_id, started_at_s=float(idx))
        store.record_request_end(request_id, duration_ms=duration)

    snapshot = store.snapshot(now_s=10.0)
    assert snapshot["request_durations_ms"] == [40, 30, 20]


def test_api_metrics_store_cleans_stale_active_requests(real_redis_client):
    store = RedisAPIMetricsStore(
        real_redis_client,
        prefix="doctoralia:test:metrics:stale",
        max_samples=5,
        active_request_ttl_s=30,
    )

    store.record_request_start("stale-request", started_at_s=10.0)
    snapshot = store.snapshot(now_s=50.0)

    assert snapshot["requests_total"] == 1
    assert snapshot["requests_in_progress"] == 0
