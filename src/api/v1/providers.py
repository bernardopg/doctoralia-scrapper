"""Dependency providers for API routers.

Keeping these providers in one module makes route handlers easier to test with
FastAPI dependency overrides and avoids binding routers directly to global
constructors.
"""

from typing import Any

from src.api.v1 import _state
from src.jobs import queue as queue_module


def get_app_config() -> Any:
    return _state.load_config()


def get_job_queue() -> Any:
    return queue_module.get_queue()


def get_job_queue_factory() -> Any:
    return queue_module.get_queue


def get_metrics_snapshot() -> tuple[dict, bool]:
    return _state.read_metrics_snapshot()


def get_running_telegram_schedule_service() -> Any:
    return _state.get_telegram_schedule_service(start_runner=True)
