import os
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.api.schemas.common import HealthResponse, ReadyComponent, ReadyResponse
from src.api.v1._state import API_VERSION
from src.api.v1.providers import get_app_config, get_job_queue_factory
from src.db.base import get_sessionmaker

router = APIRouter(tags=["Health"])

_API_START_TIME = datetime.now()


def get_api_start_time() -> datetime:
    return _API_START_TIME


@router.get("/")
async def root():
    return {"message": "Doctoralia Scrapper API", "docs": "/docs"}


@router.get("/v1/version")
async def version_info():
    return {"version": API_VERSION, "start_time": _API_START_TIME.isoformat()}


@router.get("/v1/health", response_model=HealthResponse)
async def health_check():
    uptime = int((datetime.now() - _API_START_TIME).total_seconds())
    return HealthResponse(status="ok", version=API_VERSION, uptime_s=uptime)


@router.get("/v1/ready", response_model=ReadyResponse)
async def readiness_check(
    config=Depends(get_app_config),
    queue_factory=Depends(get_job_queue_factory),
):
    components: dict[str, ReadyComponent] = {}

    redis_ok = False
    redis_error = None
    redis_latency = None
    try:
        import redis as redis_lib

        start = time.perf_counter()
        r = redis_lib.Redis.from_url(config.integrations.redis_url)
        r.ping()
        redis_latency = int((time.perf_counter() - start) * 1000)
        redis_ok = True
    except Exception as exc:  # pragma: no cover
        redis_error = str(exc)[:300]
    components["redis"] = ReadyComponent(
        status=redis_ok, latency_ms=redis_latency, error=redis_error
    )

    queue_ok = False
    queue_latency = None
    queue_error = None
    queue_details = None
    try:
        from rq.registry import FailedJobRegistry

        q = queue_factory()
        start = time.perf_counter()
        depth = q.count
        failed_registry = FailedJobRegistry(q.name, connection=q.connection)
        failed_count = len(failed_registry.get_job_ids())
        queue_latency = int((time.perf_counter() - start) * 1000)
        queue_ok = True
        queue_details = {"depth": depth, "failed": failed_count}
    except Exception as exc:  # pragma: no cover
        queue_error = str(exc)[:300]
    components["queue"] = ReadyComponent(
        status=queue_ok,
        latency_ms=queue_latency,
        error=queue_error,
        details=queue_details,
    )

    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../../")
    )
    templates_dir = os.path.join(project_root, "templates")
    tmpl_ok = os.path.isdir(templates_dir)
    components["templates"] = ReadyComponent(
        status=tmpl_ok,
        latency_ms=0,
        details={"path": templates_dir},
        error=None if tmpl_ok else "Template directory missing",
    )

    nltk_ok = False
    nltk_error = None
    try:
        from src.response_quality_analyzer import ResponseQualityAnalyzer

        _ = ResponseQualityAnalyzer()
        nltk_ok = True
    except Exception as exc:  # pragma: no cover
        nltk_error = str(exc)[:200]
    components["nltk_vader"] = ReadyComponent(
        status=nltk_ok, latency_ms=None, error=nltk_error, details=None
    )

    selenium_ok = False
    selenium_error = None
    selenium_latency = None
    try:
        selenium_url = config.integrations.selenium_remote_url
        start = time.perf_counter()
        try:
            status_endpoint = f"{selenium_url.rstrip('/')}/status"
            parsed = urlparse(status_endpoint)
            if parsed.scheme not in {"http", "https"}:
                raise ValueError("Invalid Selenium URL scheme")
            response = requests.get(status_endpoint, timeout=5)
            response.raise_for_status()
            selenium_latency = int((time.perf_counter() - start) * 1000)
            selenium_ok = True
        except requests.RequestException as e:
            selenium_error = f"Connection failed: {str(e)[:200]}"
    except Exception as exc:  # pragma: no cover
        selenium_error = str(exc)[:200]
    components["selenium"] = ReadyComponent(
        status=selenium_ok,
        latency_ms=selenium_latency,
        error=selenium_error,
        details=None,
    )

    database_ok = False
    database_error = None
    database_latency = None
    try:
        start = time.perf_counter()
        async_session = get_sessionmaker()
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        database_latency = int((time.perf_counter() - start) * 1000)
        database_ok = True
    except Exception as exc:  # pragma: no cover
        database_error = str(exc)[:300]
    components["database"] = ReadyComponent(
        status=database_ok,
        latency_ms=database_latency,
        error=database_error,
        details=None,
    )

    overall_ready = all(c.status for c in components.values())
    status_code = (
        status.HTTP_200_OK if overall_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(
        status_code=status_code,
        content=ReadyResponse(
            ready=overall_ready,
            checks={k: v.status for k, v in components.items()},
            components=components,
        ).model_dump(by_alias=True),
    )
