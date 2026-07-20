"""
Shared mutable state and singleton helpers for the API.

Centralises the module-level caches so every router imports from here
instead of re-declaring globals.
"""

import logging
import os
from typing import Optional

from src.api.v1.metrics_store import RedisAPIMetricsStore
from src.services.telegram_schedule_service import TelegramScheduleService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_VERSION = "2.4.0"

METRICS_MAX_SAMPLES = 500
METRICS_ACTIVE_REQUEST_TTL_S = 3600
METRICS_PREFIX = "doctoralia:api:metrics"
RATE_LIMIT_PREFIX = "doctoralia:api:rate_limit"
SECRET_MASK_PREFIX = "********"  # nosec B105

SCHEDULE_RUN_FAILURE_MESSAGE = "Schedule execution failed"
SCHEDULE_RUN_SUCCESS_MESSAGE = "Schedule executed successfully"
SCHEDULE_RUN_ACCEPTED_MESSAGE = (
    "Schedule execution started in background. Refresh the history in a few minutes."
)
SCHEDULE_RUN_ALREADY_RUNNING_MESSAGE = "Schedule execution is already in progress"
SCHEDULE_RUN_HEALTH_CHECK_ERROR = "Health check failed"

# ---------------------------------------------------------------------------
# Singleton caches
# ---------------------------------------------------------------------------

_metrics_store_cache: Optional[RedisAPIMetricsStore] = None
_metrics_store_cache_url: Optional[str] = None
_telegram_schedule_service: Optional[TelegramScheduleService] = None
_telegram_schedule_service_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


def load_config():
    from src.config.settings import AppConfig

    return AppConfig.load()


def is_debug_enabled() -> bool:
    try:
        return bool(load_config().api.debug)
    except Exception:
        return os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Metrics store
# ---------------------------------------------------------------------------


def get_metrics_store() -> Optional[RedisAPIMetricsStore]:
    global _metrics_store_cache, _metrics_store_cache_url

    try:
        redis_url = load_config().integrations.redis_url
    except Exception:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    if not redis_url:
        return None

    if _metrics_store_cache is None or _metrics_store_cache_url != redis_url:
        _metrics_store_cache = RedisAPIMetricsStore.from_url(
            redis_url,
            prefix=METRICS_PREFIX,
            max_samples=METRICS_MAX_SAMPLES,
            active_request_ttl_s=METRICS_ACTIVE_REQUEST_TTL_S,
        )
        _metrics_store_cache_url = redis_url

    return _metrics_store_cache


# ---------------------------------------------------------------------------
# Telegram schedule service
# ---------------------------------------------------------------------------


def should_disable_notification_scheduler() -> bool:
    if os.getenv("DISABLE_NOTIFICATION_SCHEDULER", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def get_telegram_schedule_service(
    start_runner: bool = False,
) -> TelegramScheduleService:
    global _telegram_schedule_service, _telegram_schedule_service_url

    config = load_config()
    redis_url = config.integrations.redis_url or os.getenv(
        "REDIS_URL", "redis://localhost:6379/0"
    )

    if (
        _telegram_schedule_service is None
        or _telegram_schedule_service_url != redis_url
    ):
        _telegram_schedule_service = TelegramScheduleService(
            logger=logger,
            config_loader=load_config,
        )
        _telegram_schedule_service_url = redis_url

    if start_runner and not should_disable_notification_scheduler():
        _telegram_schedule_service.start()

    return _telegram_schedule_service


def stop_telegram_schedule_service() -> None:
    if _telegram_schedule_service is not None:
        _telegram_schedule_service.stop()


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------


def record_request_start_metric(request_id: str, started_at_s: float) -> None:
    try:
        store = get_metrics_store()
        if store is not None:
            store.record_request_start(request_id, started_at_s)
    except Exception as exc:  # pragma: no cover
        logger.debug("Unable to record request start metric: %s", exc)


def record_request_end_metric(
    request_id: str, duration_ms: int, failed: bool = False
) -> None:
    try:
        store = get_metrics_store()
        if store is not None:
            store.record_request_end(request_id, duration_ms, failed=failed)
    except Exception as exc:  # pragma: no cover
        logger.debug("Unable to record request end metric: %s", exc)


def increment_analysis_metric(amount: int = 1) -> None:
    try:
        store = get_metrics_store()
        if store is not None:
            store.increment_analysis(amount)
    except Exception as exc:  # pragma: no cover
        logger.debug("Unable to increment analysis metric: %s", exc)


def increment_generation_metric(amount: int = 1) -> None:
    try:
        store = get_metrics_store()
        if store is not None:
            store.increment_generation(amount)
    except Exception as exc:  # pragma: no cover
        logger.debug("Unable to increment generation metric: %s", exc)


def increment_scrapes_metric(amount: int = 1) -> None:
    try:
        store = get_metrics_store()
        if store is not None:
            store.increment_scrapes(amount)
    except Exception as exc:  # pragma: no cover
        logger.debug("Unable to increment scrapes metric: %s", exc)


def increment_scrapes_failed_metric(amount: int = 1) -> None:
    try:
        store = get_metrics_store()
        if store is not None:
            store.increment_scrapes_failed(amount)
    except Exception as exc:  # pragma: no cover
        logger.debug("Unable to increment failed scrapes metric: %s", exc)


def empty_metrics_snapshot() -> dict:
    return {
        "requests_total": 0,
        "requests_in_progress": 0,
        "requests_failed_total": 0,
        "scrapes_total": 0,
        "scrapes_failed_total": 0,
        "generation_total": 0,
        "analysis_total": 0,
        "request_durations_ms": [],
    }


def read_metrics_snapshot() -> tuple[dict, bool]:
    try:
        store = get_metrics_store()
        if store is None:
            return empty_metrics_snapshot(), False
        return store.snapshot(), True
    except Exception as exc:  # pragma: no cover
        logger.debug("Unable to read metrics snapshot: %s", exc)
        return empty_metrics_snapshot(), False


# ---------------------------------------------------------------------------
# Secret helpers
# ---------------------------------------------------------------------------


def mask_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    suffix = value[-4:] if len(value) >= 4 else "set"
    return f"{SECRET_MASK_PREFIX}{suffix}"


def is_masked_secret(value: Optional[str]) -> bool:
    return bool(value and value.startswith(SECRET_MASK_PREFIX))
