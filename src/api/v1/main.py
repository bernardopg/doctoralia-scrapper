"""
Main API module for n8n integration.
"""

import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Optional, cast  # noqa: F401 (kept for future extensibility)
from urllib.parse import urlparse

import redis
import requests
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    GeneratedResponsePreview,
    HealthResponse,
    ReadyComponent,
    ReadyResponse,
    UnifiedResult,
)
from src.api.schemas.notifications import (
    TelegramNotificationHistoryResponse,
    TelegramNotificationRunResponse,
    TelegramNotificationScheduleListResponse,
    TelegramNotificationScheduleModel,
    TelegramNotificationTestRequest,
)
from src.api.schemas.requests import (
    GenerateResponseRequest,
    JobCreateRequest,
    JobResponse,
    ScrapeRequest,
    WebhookRequest,
    WebhookResponse,
)
from src.api.schemas.settings import (
    BatchQualityAnalysisRequest,
    QualityAnalysisRequest,
    QualityAnalysisResponse,
    SettingsModel,
    SettingsResponse,
    StatisticsResponse,
)
from src.api.v1.deps import require_api_key, verify_webhook_signature
from src.api.v1.metrics_store import RedisAPIMetricsStore
from src.integrations.n8n.normalize import extract_scraper_result, make_unified_result
from src.jobs.queue import get_queue
from src.jobs.tasks import scrape_and_process
from src.services.telegram_schedule_service import TelegramScheduleService

# API metadata
API_VERSION = "1.2.0-rc.1"
API_START_TIME = datetime.now()
logger = logging.getLogger(__name__)

METRICS_MAX_SAMPLES = 500
METRICS_ACTIVE_REQUEST_TTL_S = 3600
METRICS_PREFIX = "doctoralia:api:metrics"
_metrics_store_cache: Optional[RedisAPIMetricsStore] = None
_metrics_store_cache_url: Optional[str] = None
_telegram_schedule_service: Optional[TelegramScheduleService] = None
_telegram_schedule_service_url: Optional[str] = None

# Create FastAPI app
app = FastAPI(
    title="Doctoralia Scrapper API",
    description="n8n-compatible API for scraping and analyzing medical reviews",
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_notification_scheduler() -> None:
    if _should_disable_notification_scheduler():
        return
    _get_telegram_schedule_service(start_runner=True)


@app.on_event("shutdown")
async def shutdown_notification_scheduler() -> None:
    global _telegram_schedule_service
    if _telegram_schedule_service is not None:
        _telegram_schedule_service.stop()


def start_api(
    host: str = "127.0.0.1", port: int = 8000
):  # pragma: no cover - thin wrapper
    """Convenience wrapper so the CLI can start the API without importing uvicorn everywhere.

    We import uvicorn lazily to avoid the dependency being required for users
    who do not run the API component.
    """
    import importlib.util

    uvicorn_spec = importlib.util.find_spec("uvicorn")
    if uvicorn_spec is None:
        raise RuntimeError(
            "uvicorn is required to start the API. Install with 'poetry add uvicorn' or pip."
        )

    import uvicorn  # type: ignore

    uvicorn.run(app, host=host, port=port)


def _load_config():
    """Load AppConfig (helper to avoid repetition)."""
    from config.settings import AppConfig

    return AppConfig.load()


def _is_debug_enabled() -> bool:
    try:
        return bool(_load_config().api.debug)
    except Exception:
        return os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _get_metrics_store() -> Optional[RedisAPIMetricsStore]:
    """Reuse one Redis-backed metrics store per effective Redis URL."""
    global _metrics_store_cache, _metrics_store_cache_url

    try:
        redis_url = _load_config().integrations.redis_url
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


def _should_disable_notification_scheduler() -> bool:
    if os.getenv("DISABLE_NOTIFICATION_SCHEDULER", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def _get_telegram_schedule_service(
    start_runner: bool = False,
) -> TelegramScheduleService:
    global _telegram_schedule_service, _telegram_schedule_service_url

    config = _load_config()
    redis_url = config.integrations.redis_url or os.getenv(
        "REDIS_URL", "redis://localhost:6379/0"
    )

    if (
        _telegram_schedule_service is None
        or _telegram_schedule_service_url != redis_url
    ):
        _telegram_schedule_service = TelegramScheduleService(
            logger=logger,
            config_loader=_load_config,
        )
        _telegram_schedule_service_url = redis_url

    if start_runner and not _should_disable_notification_scheduler():
        _telegram_schedule_service.start()

    return _telegram_schedule_service


def _record_request_start_metric(request_id: str, started_at_s: float) -> None:
    try:
        metrics_store = _get_metrics_store()
        if metrics_store is not None:
            metrics_store.record_request_start(request_id, started_at_s)
    except Exception as exc:  # pragma: no cover - redis/network dependent
        logger.debug("Unable to record request start metric: %s", exc)


def _record_request_end_metric(
    request_id: str, duration_ms: int, failed: bool = False
) -> None:
    try:
        metrics_store = _get_metrics_store()
        if metrics_store is not None:
            metrics_store.record_request_end(request_id, duration_ms, failed=failed)
    except Exception as exc:  # pragma: no cover - redis/network dependent
        logger.debug("Unable to record request end metric: %s", exc)


def _increment_analysis_metric(amount: int = 1) -> None:
    try:
        metrics_store = _get_metrics_store()
        if metrics_store is not None:
            metrics_store.increment_analysis(amount)
    except Exception as exc:  # pragma: no cover - redis/network dependent
        logger.debug("Unable to increment analysis metric: %s", exc)


def _increment_generation_metric(amount: int = 1) -> None:
    try:
        metrics_store = _get_metrics_store()
        if metrics_store is not None:
            metrics_store.increment_generation(amount)
    except Exception as exc:  # pragma: no cover - redis/network dependent
        logger.debug("Unable to increment generation metric: %s", exc)


def _increment_scrapes_metric(amount: int = 1) -> None:
    try:
        metrics_store = _get_metrics_store()
        if metrics_store is not None:
            metrics_store.increment_scrapes(amount)
    except Exception as exc:  # pragma: no cover - redis/network dependent
        logger.debug("Unable to increment scrapes metric: %s", exc)


def _increment_scrapes_failed_metric(amount: int = 1) -> None:
    try:
        metrics_store = _get_metrics_store()
        if metrics_store is not None:
            metrics_store.increment_scrapes_failed(amount)
    except Exception as exc:  # pragma: no cover - redis/network dependent
        logger.debug("Unable to increment failed scrapes metric: %s", exc)


def _empty_metrics_snapshot() -> dict[str, Any]:
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


def _read_metrics_snapshot() -> tuple[dict[str, Any], bool]:
    try:
        metrics_store = _get_metrics_store()
        if metrics_store is None:
            return _empty_metrics_snapshot(), False
        return metrics_store.snapshot(), True
    except Exception as exc:  # pragma: no cover - redis/network dependent
        logger.debug("Unable to read metrics snapshot: %s", exc)
        return _empty_metrics_snapshot(), False


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID, collect basic metrics, and structured timing headers."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started_at_s = time.time()
    start_time = time.perf_counter()
    failed = False
    _record_request_start_metric(request_id, started_at_s)
    try:
        response = await call_next(request)
    except Exception:
        failed = True
        raise
    finally:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        _record_request_end_metric(request_id, duration_ms, failed=failed)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Response-Time-ms"] = str(duration_ms)
    return response


# Exception handlers
@app.exception_handler(status.HTTP_400_BAD_REQUEST)
async def bad_request_handler(request: Request, exc: HTTPException):
    """Handle 400 errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error=ErrorDetail(
                code="BAD_REQUEST",
                message=str(exc.detail),
                details=None,
                request_id=getattr(request.state, "request_id", None),
            )
        ).dict(),
    )


@app.exception_handler(status.HTTP_401_UNAUTHORIZED)
async def unauthorized_handler(request: Request, exc: HTTPException):
    """Handle 401 errors."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorResponse(
            error=ErrorDetail(
                code="UNAUTHORIZED",
                message=str(exc.detail),
                details=None,
                request_id=getattr(request.state, "request_id", None),
            )
        ).dict(),
    )


@app.exception_handler(status.HTTP_404_NOT_FOUND)
async def not_found_handler(request: Request, exc: HTTPException):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorResponse(
            error=ErrorDetail(
                code="NOT_FOUND",
                message=str(exc.detail),
                details=None,
                request_id=getattr(request.state, "request_id", None),
            )
        ).dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_ERROR",
                message="An internal error occurred",
                details=str(exc) if _is_debug_enabled() else None,
                request_id=getattr(request.state, "request_id", None),
            )
        ).dict(),
    )


# Health check endpoints
@app.get("/v1/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    uptime = int((datetime.now() - API_START_TIME).total_seconds())

    return HealthResponse(
        status="ok",
        version=API_VERSION,
        uptime_s=uptime,
    )


@app.get("/v1/ready", response_model=ReadyResponse, tags=["Health"])
async def readiness_check():
    """Readiness check endpoint with component diagnostics.

    Components:
      - redis: connectivity + ping latency
      - queue: depth & failed job count (best effort)
      - templates: presence of template directory
      - nltk: VADER resource availability (heuristic)
      - selenium: assumed ready unless explicit failures tracked (placeholder)
    """
    components: dict[str, ReadyComponent] = {}
    config = _load_config()

    # Redis connectivity & latency
    redis_ok = False
    redis_error = None
    redis_latency = None
    try:
        start = time.perf_counter()
        r = redis.Redis.from_url(config.integrations.redis_url)
        r.ping()
        redis_latency = int((time.perf_counter() - start) * 1000)
        redis_ok = True
    except Exception as exc:  # pragma: no cover - network/env dependent
        redis_error = str(exc)[:300]
    components["redis"] = ReadyComponent(
        status=redis_ok, latency_ms=redis_latency, error=redis_error
    )

    # Queue depth (RQ)
    queue_ok = False
    queue_latency = None
    queue_error = None
    queue_details = None
    try:
        from rq.registry import FailedJobRegistry

        q = get_queue()
        start = time.perf_counter()
        depth = q.count
        failed_registry = FailedJobRegistry(q.name, connection=q.connection)
        failed_count = len(failed_registry.get_job_ids())
        queue_latency = int((time.perf_counter() - start) * 1000)
        queue_ok = True
        queue_details = {"depth": depth, "failed": failed_count}
    except Exception as exc:  # pragma: no cover - environment dependent
        queue_error = str(exc)[:300]
    components["queue"] = ReadyComponent(
        status=queue_ok,
        latency_ms=queue_latency,
        error=queue_error,
        details=queue_details,
    )

    # Templates directory existence
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    templates_dir = os.path.join(project_root, "templates")
    tmpl_ok = os.path.isdir(templates_dir)
    components["templates"] = ReadyComponent(
        status=tmpl_ok,
        latency_ms=0,
        details={"path": templates_dir},
        error=None if tmpl_ok else "Template directory missing",
    )

    # NLTK VADER availability (heuristic)
    nltk_ok = False
    nltk_error = None
    try:
        from src.response_quality_analyzer import ResponseQualityAnalyzer

        _ = (
            ResponseQualityAnalyzer()
        )  # will download if missing (may be slow first time)
        nltk_ok = True
    except Exception as exc:  # pragma: no cover - network/download dependent
        nltk_error = str(exc)[:200]
    components["nltk_vader"] = ReadyComponent(
        status=nltk_ok, latency_ms=None, error=nltk_error, details=None
    )

    # Selenium readiness check with real connection test
    selenium_ok = False
    selenium_error = None
    selenium_latency = None
    try:
        selenium_url = config.integrations.selenium_remote_url
        start = time.perf_counter()

        # Create a simple HTTP request to check if Selenium is responding
        try:
            status_endpoint = f"{selenium_url.rstrip('/')}/status"
            parsed = urlparse(status_endpoint)
            if parsed.scheme not in {"http", "https"}:
                raise ValueError("Invalid Selenium URL scheme")

            # Use timeout to avoid blocking health checks.
            response = requests.get(status_endpoint, timeout=5)
            response.raise_for_status()
            selenium_latency = int((time.perf_counter() - start) * 1000)
            selenium_ok = True
        except requests.RequestException as e:
            selenium_error = f"Connection failed: {str(e)[:200]}"
    except Exception as exc:  # pragma: no cover - network/config dependent
        selenium_error = str(exc)[:200]
    components["selenium"] = ReadyComponent(
        status=selenium_ok,
        latency_ms=selenium_latency,
        error=selenium_error,
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
        ).dict(by_alias=True),
    )


# Synchronous scraping endpoint
@app.post(
    "/v1/scrape:run",
    response_model=UnifiedResult,
    dependencies=[Depends(require_api_key)],
    tags=["Scraping"],
)
async def scrape_run(request: ScrapeRequest):
    """
    Synchronous scraping endpoint for n8n HTTP Request node.
    Returns complete results immediately.
    """
    start_time = datetime.now()

    try:
        # Import scraper here to avoid circular imports
        from config.settings import AppConfig
        from src.scraper import DoctoraliaScraper

        # Load config
        config = AppConfig.load()

        # Initialize scraper with config
        scraper = DoctoraliaScraper(config)

        # Run scraping
        scraper_result = scraper.scrape_reviews(str(request.doctor_url))

        # Extract data (scraper_result may be None on failure)
        if not scraper_result:
            raise RuntimeError("Scraper returned no data")
        doctor_data, reviews_data = extract_scraper_result(scraper_result)

        # Run analysis if requested
        analysis_data = None
        if request.include_analysis:
            from src.response_quality_analyzer import ResponseQualityAnalyzer

            analyzer = ResponseQualityAnalyzer()
            # Analyze all reviews
            sentiments = []
            for review in reviews_data:
                # analyzer has analyze_sentiment(review_text)
                review_text = review.get("comment", "")
                if review_text:
                    # Use analyzer's internal sentiment intensity analyzer directly
                    sia_scores = analyzer.sia.polarity_scores(review_text)
                    sentiments.append(
                        {
                            "compound": sia_scores.get("compound", 0.0),
                            "pos": sia_scores.get("pos", 0.0),
                            "neu": sia_scores.get("neu", 0.0),
                            "neg": sia_scores.get("neg", 0.0),
                        }
                    )

            # Aggregate sentiment
            if sentiments:
                avg_sentiment = {
                    "compound": sum(s["compound"] for s in sentiments)
                    / len(sentiments),
                    "pos": sum(s["pos"] for s in sentiments) / len(sentiments),
                    "neu": sum(s["neu"] for s in sentiments) / len(sentiments),
                    "neg": sum(s["neg"] for s in sentiments) / len(sentiments),
                }
            else:
                avg_sentiment = {"compound": 0, "pos": 0, "neu": 0, "neg": 0}

            analysis_data = {
                "summary": f"Analyzed {len(reviews_data)} reviews",
                "sentiment": avg_sentiment,
                "quality_score": avg_sentiment["compound"] * 100,
                "flags": [],
            }

        # Run generation if requested
        generation_data = None
        if request.include_generation:
            from src.response_generator import ResponseGenerator

            generator = ResponseGenerator(config, logger=None)
            responses = []
            for idx, review in enumerate(reviews_data):
                try:
                    generation_result = generator.generate_response_with_metadata(
                        review,
                        doctor_context=doctor_data,
                        generation_mode=request.generation_mode,
                        language=request.language or "pt-BR",
                    )
                except Exception:
                    generation_result = {
                        "text": "",
                        "model": {
                            "type": "error",
                            "provider": request.generation_mode
                            or config.generation.mode,
                        },
                    }
                responses.append(
                    {
                        "review_id": str(review.get("id", idx)),
                        "text": generation_result["text"],
                        "language": request.language or "pt",
                        "provider": generation_result["model"].get("provider"),
                        "model": generation_result["model"].get("name"),
                        "fallback_used": generation_result["model"].get("mode")
                        == "local"
                        and (request.generation_mode or config.generation.mode)
                        != "local",
                        "status": "generated" if generation_result["text"] else "empty",
                    }
                )
            generation_data = {
                "template_id": request.response_template_id,
                "responses": responses,
                "model": {
                    "type": "batch",
                    "provider": request.generation_mode or config.generation.mode,
                },
            }

        # Create unified result and return
        _increment_scrapes_metric()
        if request.include_analysis:
            _increment_analysis_metric()
        if request.include_generation:
            _increment_generation_metric()
        return make_unified_result(
            doctor_data=doctor_data,
            reviews_data=reviews_data,
            analysis_data=analysis_data,
            generation_data=generation_data,
            status="completed",
            start_time=start_time,
            end_time=datetime.now(),
        )

    except Exception:
        _increment_scrapes_failed_metric()
        return make_unified_result(
            doctor_data={"name": "Error", "url": str(request.doctor_url)},
            reviews_data=[],
            status="failed",
            start_time=start_time,
            end_time=datetime.now(),
        )


@app.post(
    "/v1/generate/response",
    response_model=GeneratedResponsePreview,
    dependencies=[Depends(require_api_key)],
    tags=["Generation"],
)
async def generate_single_response(request: GenerateResponseRequest):
    """Generate one response suggestion using the configured mode or an override."""
    from src.response_generator import ResponseGenerator

    config = _load_config()
    generator = ResponseGenerator(config, logger=None)
    review = {
        "id": request.review_id,
        "author": request.author,
        "comment": request.comment,
        "rating": request.rating,
        "date": request.date,
    }
    doctor_context = {
        "name": request.doctor_name,
        "specialty": request.doctor_specialty,
        "profile_url": (
            str(request.doctor_profile_url) if request.doctor_profile_url else None
        ),
    }

    try:
        result = generator.generate_response_with_metadata(
            review,
            doctor_context=doctor_context,
            generation_mode=request.generation_mode,
            language=request.language or "pt-BR",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate response: {exc}",
        ) from exc

    _increment_generation_metric()
    return GeneratedResponsePreview(
        review_id=request.review_id,
        text=result["text"],
        model=result["model"],
    )


# Async job endpoints
@app.post(
    "/v1/jobs",
    response_model=JobResponse,
    dependencies=[Depends(require_api_key)],
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Jobs"],
)
async def create_job(request: JobCreateRequest):
    """
    Create an async scraping job.
    Returns job ID for polling.
    """
    # Get or create job ID
    config = _load_config()
    if request.idempotency_key:
        r = redis.Redis.from_url(config.integrations.redis_url)
        existing_job_id = cast(
            bytes | str | None, r.get(f"idem:{request.idempotency_key}")
        )
        if existing_job_id:
            return JobResponse(
                job_id=(
                    existing_job_id.decode()
                    if isinstance(existing_job_id, bytes)
                    else existing_job_id
                ),
                status="queued",
                message="Job already exists",
            )

    # Create new job
    job_id = str(uuid.uuid4())

    # Enqueue job
    q = get_queue()
    q.enqueue(
        scrape_and_process,
        request.dict(),
        job_id,
        str(request.callback_url) if request.callback_url else None,
        job_id=job_id,
    )

    # Store idempotency key if provided
    if request.idempotency_key:
        r = redis.Redis.from_url(config.integrations.redis_url)
        r.setex(f"idem:{request.idempotency_key}", 3600, job_id)

    return JobResponse(
        job_id=job_id,
        status="queued",
        message="Job created successfully",
    )


def _map_job_status(job: Any) -> str:
    """Map RQ job state to API status values used by the dashboard."""
    result_status: Optional[str] = None
    result = getattr(job, "result", None)
    if isinstance(result, dict):
        raw_status = result.get("status")
        if isinstance(raw_status, str):
            result_status = raw_status
    elif result is not None:
        raw_status = getattr(result, "status", None)
        if isinstance(raw_status, str):
            result_status = raw_status

    if job.is_queued or job.is_deferred:
        return "pending"
    if job.is_started:
        return "running"
    if job.is_finished and result_status in {"completed", "failed"}:
        return result_status
    if job.is_failed:
        return "failed"
    if job.is_finished:
        return "completed"
    return "unknown"


@app.get(
    "/v1/jobs",
    dependencies=[Depends(require_api_key)],
    tags=["Jobs"],
)
async def list_jobs(status_filter: Optional[str] = Query(default=None, alias="status")):
    """
    List all async jobs, optionally filtered by status.
    """
    from rq.registry import FailedJobRegistry, FinishedJobRegistry, StartedJobRegistry

    q = get_queue()
    job_ids = set()
    normalized_filter = (status_filter or "").strip().lower()
    if normalized_filter == "queued":
        normalized_filter = "pending"

    if not normalized_filter or normalized_filter == "pending":
        job_ids.update(q.job_ids)
    if not normalized_filter or normalized_filter == "running":
        job_ids.update(StartedJobRegistry(queue=q).get_job_ids())
    if not normalized_filter or normalized_filter in {"completed", "failed"}:
        job_ids.update(FinishedJobRegistry(queue=q).get_job_ids())
    if not normalized_filter or normalized_filter == "failed":
        job_ids.update(FailedJobRegistry(queue=q).get_job_ids())

    jobs = []
    # Limit to 100 jobs to avoid performance issues
    for jid in list(job_ids)[:100]:
        job = q.fetch_job(jid)
        if not job:
            continue

        job_status = _map_job_status(job)
        if normalized_filter and job_status != normalized_filter:
            continue

        progress = job.meta.get("progress", 0) if job.meta else 0
        if job_status == "completed":
            progress = 100

        jobs.append(
            {
                "task_id": job.id,
                "status": job_status,
                "progress": progress,
                "message": job.meta.get("message", "") if job.meta else "",
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
                "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            }
        )

    # Sort by created_at descending
    jobs.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return jobs


@app.get(
    "/v1/jobs/{job_id}",
    response_model=UnifiedResult,
    dependencies=[Depends(require_api_key)],
    tags=["Jobs"],
)
async def get_job_status(job_id: str):
    """
    Get job status and results.
    """
    q = get_queue()
    job = q.fetch_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Map RQ status to our status
    job_status = _map_job_status(job)

    # Return result if available
    if job.result and (job.is_finished or job.is_failed):
        return job.result

    # Return status placeholder
    return make_unified_result(
        doctor_data={"name": "Processing", "url": ""},
        reviews_data=[],
        job_id=job_id,
        status=job_status,
    )


# Webhook endpoint
@app.post(
    "/v1/hooks/n8n/scrape",
    response_model=WebhookResponse,
    tags=["Webhooks"],
)
async def webhook_scrape(
    request: WebhookRequest,
    req: Request,
    _: bool = Depends(verify_webhook_signature),
):
    """
    Webhook endpoint for n8n triggers.
    Enqueues job and returns acknowledgment.
    """
    # Create job from webhook request
    job_request = JobCreateRequest(
        doctor_url=request.doctor_url,
        include_analysis=request.include_analysis,
        include_generation=request.include_generation,
        response_template_id=request.response_template_id,
        language=request.language,
        mode="async",
        callback_url=request.callback_url,
        meta=None,
        idempotency_key=None,
    )

    # Enqueue job
    job_response = await create_job(job_request)

    return WebhookResponse(
        received=True,
        job_id=job_response.job_id,
        status=job_response.status,
    )


# Root redirect
@app.get("/")
async def root():
    """Redirect to docs."""
    return {"message": "Doctoralia Scrapper API", "docs": "/docs"}


@app.get("/v1/version", tags=["Health"])  # Simple version endpoint
async def version_info():
    return {"version": API_VERSION, "start_time": API_START_TIME.isoformat()}


def _percentile(data: list[int], pct: float) -> Optional[float]:  # helper
    if not data:
        return None
    idx = int(round((len(data) - 1) * pct))
    return sorted(data)[idx]


@app.get("/v1/metrics", tags=["Metrics"])  # lightweight metrics endpoint
async def metrics_endpoint():
    """Return Redis-backed API metrics suitable for multi-process deployments."""
    snapshot, redis_available = _read_metrics_snapshot()
    durations: list[int] = snapshot["request_durations_ms"]  # type: ignore[assignment]
    body = {
        "version": API_VERSION,
        "uptime_s": int((datetime.now() - API_START_TIME).total_seconds()),
        "backend": {"type": "redis", "available": redis_available},
        "requests": {
            "total": snapshot["requests_total"],
            "in_progress": snapshot["requests_in_progress"],
            "failed": snapshot["requests_failed_total"],
            "p50_ms": _percentile(durations, 0.50),
            "p95_ms": _percentile(durations, 0.95),
            "p99_ms": _percentile(durations, 0.99),
            "latest_ms": durations[0] if durations else None,
            "sample_size": len(durations),
        },
        "scraping": {
            "scrapes_total": snapshot["scrapes_total"],
            "scrapes_failed_total": snapshot["scrapes_failed_total"],
            "analysis_total": snapshot["analysis_total"],
            "generation_total": snapshot["generation_total"],
        },
    }
    return body


@app.get(
    "/v1/notifications/telegram/schedules",
    response_model=TelegramNotificationScheduleListResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Notifications"],
)
async def list_telegram_notification_schedules():
    service = _get_telegram_schedule_service(start_runner=True)
    return {
        "schedules": service.list_schedules(),
        "summary": service.get_summary(),
    }


@app.post(
    "/v1/notifications/telegram/schedules",
    response_model=dict,
    dependencies=[Depends(require_api_key)],
    tags=["Notifications"],
)
async def create_telegram_notification_schedule(
    schedule: TelegramNotificationScheduleModel,
):
    try:
        service = _get_telegram_schedule_service(start_runner=True)
        saved = service.save_schedule(schedule.model_dump())
        return {"success": True, "schedule": saved}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put(
    "/v1/notifications/telegram/schedules/{schedule_id}",
    response_model=dict,
    dependencies=[Depends(require_api_key)],
    tags=["Notifications"],
)
async def update_telegram_notification_schedule(
    schedule_id: str,
    schedule: TelegramNotificationScheduleModel,
):
    try:
        service = _get_telegram_schedule_service(start_runner=True)
        if service.get_schedule(schedule_id) is None:
            raise HTTPException(status_code=404, detail="Schedule not found")
        saved = service.save_schedule(schedule.model_dump(), schedule_id=schedule_id)
        return {"success": True, "schedule": saved}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete(
    "/v1/notifications/telegram/schedules/{schedule_id}",
    response_model=dict,
    dependencies=[Depends(require_api_key)],
    tags=["Notifications"],
)
async def delete_telegram_notification_schedule(schedule_id: str):
    service = _get_telegram_schedule_service(start_runner=True)
    deleted = service.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True}


@app.post(
    "/v1/notifications/telegram/schedules/{schedule_id}/run",
    response_model=TelegramNotificationRunResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Notifications"],
)
async def run_telegram_notification_schedule(schedule_id: str):
    try:
        service = _get_telegram_schedule_service(start_runner=True)
        result = service.execute_schedule(schedule_id, manual=True)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/v1/notifications/telegram/history",
    response_model=TelegramNotificationHistoryResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Notifications"],
)
async def list_telegram_notification_history(
    limit: int = Query(default=50, ge=1, le=200)
):
    service = _get_telegram_schedule_service(start_runner=True)
    return {"history": service.list_history(limit=limit)}


@app.post(
    "/v1/notifications/telegram/test",
    response_model=TelegramNotificationRunResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Notifications"],
)
async def send_test_telegram_notification(payload: TelegramNotificationTestRequest):
    service = _get_telegram_schedule_service(start_runner=True)
    result = service.send_test_notification(
        message=payload.message,
        telegram_token=payload.telegram_token,
        telegram_chat_id=payload.telegram_chat_id,
        parse_mode=payload.parse_mode or "Markdown",
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# ---------------------------------------------------------------------------
# Statistics endpoint
# ---------------------------------------------------------------------------


@app.get(
    "/v1/statistics",
    response_model=StatisticsResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Monitoring"],
)
async def get_statistics():
    """Get comprehensive scraping statistics from data files."""
    from config.settings import AppConfig
    from src.services.stats import StatsService

    config = AppConfig.load()
    svc = StatsService(config.data_dir)
    stats = svc.get_scraper_stats()
    return StatisticsResponse(**stats)


# ---------------------------------------------------------------------------
# Quality Analysis endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/v1/analyze/quality",
    response_model=QualityAnalysisResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Analysis"],
)
async def analyze_quality(request: QualityAnalysisRequest):
    """Analyze the quality of a doctor's response."""
    from src.response_quality_analyzer import ResponseQualityAnalyzer

    analyzer = ResponseQualityAnalyzer()
    analysis = analyzer.analyze_response(request.response_text, request.original_review)
    _increment_analysis_metric()
    return QualityAnalysisResponse(
        score=analysis.score.to_dict(),
        strengths=analysis.strengths,
        weaknesses=analysis.weaknesses,
        suggestions=analysis.suggestions,
        keywords=analysis.keywords,
        sentiment=analysis.sentiment,
        readability_score=analysis.readability_score,
    )


@app.post(
    "/v1/analyze/quality/batch",
    response_model=list[QualityAnalysisResponse],
    dependencies=[Depends(require_api_key)],
    tags=["Analysis"],
)
async def analyze_quality_batch(request: BatchQualityAnalysisRequest):
    """Analyze the quality of multiple doctor's responses."""
    from src.response_quality_analyzer import ResponseQualityAnalyzer

    analyzer = ResponseQualityAnalyzer()
    results: list[QualityAnalysisResponse] = []
    for item in request.analyses:
        analysis = analyzer.analyze_response(item.response_text, item.original_review)
        results.append(
            QualityAnalysisResponse(
                score=analysis.score.to_dict(),
                strengths=analysis.strengths,
                weaknesses=analysis.weaknesses,
                suggestions=analysis.suggestions,
                keywords=analysis.keywords,
                sentiment=analysis.sentiment,
                readability_score=analysis.readability_score,
            )
        )
    _increment_analysis_metric(len(results))
    return results


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------


def _config_to_settings_model(config) -> SettingsModel:
    """Convert an AppConfig object to a SettingsModel."""
    from src.api.schemas.settings import (
        APISettingsModel,
        DelaySettingsModel,
        FavoriteProfileModel,
        GenerationSettingsModel,
        IntegrationSettingsModel,
        PrivacySettingsModel,
        ScrapingSettingsModel,
        SecuritySettingsModel,
        TelegramSettingsModel,
        URLSettingsModel,
        UserProfileSettingsModel,
    )

    return SettingsModel(
        telegram=TelegramSettingsModel(
            enabled=config.telegram.enabled,
            token=config.telegram.token,
            chat_id=config.telegram.chat_id,
            parse_mode=config.telegram.parse_mode,
            attach_responses_auto=config.telegram.attach_responses_auto,
            attachment_format=config.telegram.attachment_format,
        ),
        scraping=ScrapingSettingsModel(
            headless=config.scraping.headless,
            timeout=config.scraping.timeout,
            delay_min=config.scraping.delay_min,
            delay_max=config.scraping.delay_max,
            max_retries=config.scraping.max_retries,
            page_load_timeout=config.scraping.page_load_timeout,
            implicit_wait=config.scraping.implicit_wait,
            explicit_wait=config.scraping.explicit_wait,
        ),
        delays=DelaySettingsModel(
            human_like_min=config.delays.human_like_min,
            human_like_max=config.delays.human_like_max,
            retry_base=config.delays.retry_base,
            error_recovery=config.delays.error_recovery,
            rate_limit_retry=config.delays.rate_limit_retry,
            page_load_retry=config.delays.page_load_retry,
        ),
        api=APISettingsModel(
            host=config.api.host,
            port=config.api.port,
            debug=config.api.debug,
            workers=config.api.workers,
        ),
        security=SecuritySettingsModel(
            api_key=config.security.api_key,
            webhook_signing_secret=config.security.webhook_signing_secret,
            openai_api_key=config.security.openai_api_key,
        ),
        generation=GenerationSettingsModel(
            mode=config.generation.mode,
            openai_api_key=config.generation.openai_api_key,
            openai_model=config.generation.openai_model,
            gemini_api_key=config.generation.gemini_api_key,
            gemini_model=config.generation.gemini_model,
            claude_api_key=config.generation.claude_api_key,
            claude_model=config.generation.claude_model,
            temperature=config.generation.temperature,
            max_tokens=config.generation.max_tokens,
            system_prompt=config.generation.system_prompt,
        ),
        integrations=IntegrationSettingsModel(
            redis_url=config.integrations.redis_url,
            selenium_remote_url=config.integrations.selenium_remote_url,
            api_url=config.integrations.api_url,
            api_public_url=config.integrations.api_public_url,
        ),
        privacy=PrivacySettingsModel(
            mask_pii=config.privacy.mask_pii,
            id_salt=config.privacy.id_salt,
            job_result_ttl=config.privacy.job_result_ttl,
            rate_limit_requests=config.privacy.rate_limit_requests,
            rate_limit_window=config.privacy.rate_limit_window,
            require_tls_callbacks=config.privacy.require_tls_callbacks,
            allowed_callback_domains=config.privacy.allowed_callback_domains,
        ),
        urls=URLSettingsModel(
            base_url=config.urls.base_url,
            profile_url=config.urls.profile_url,
        ),
        user_profile=UserProfileSettingsModel(
            display_name=config.user_profile.display_name,
            username=config.user_profile.username,
            favorite_profiles=[
                FavoriteProfileModel(
                    name=profile.name,
                    profile_url=profile.profile_url,
                    specialty=profile.specialty,
                    notes=profile.notes,
                )
                for profile in config.user_profile.favorite_profiles
            ],
        ),
    )


def _is_http_url(value: Optional[str]) -> bool:
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _validate_settings(settings: SettingsModel) -> dict:
    """Validate settings and return {valid: bool, errors: list[str]}."""
    from src.secure_config import ConfigValidator

    errors: list[str] = []
    valid_generation_modes = {"local", "openai", "gemini", "claude"}

    if settings.scraping.delay_min > settings.scraping.delay_max:
        errors.append("delay_min cannot be greater than delay_max")
    if settings.scraping.timeout < 10:
        errors.append("Timeout must be at least 10 seconds")
    if settings.scraping.max_retries < 1:
        errors.append("max_retries must be at least 1")
    if settings.api.port < 1024 or settings.api.port > 65535:
        errors.append("API port must be between 1024 and 65535")
    if settings.api.workers < 1:
        errors.append("Workers must be at least 1")
    if settings.delays.human_like_min > settings.delays.human_like_max:
        errors.append("human_like_min cannot be greater than human_like_max")
    if settings.telegram.token and not settings.telegram.chat_id:
        errors.append("chat_id is required when telegram token is provided")
    if settings.telegram.enabled and not ConfigValidator.validate_telegram_config(
        settings.telegram.token, settings.telegram.chat_id
    ):
        errors.append("Enabled Telegram requires a valid token and chat_id")
    if settings.telegram.parse_mode not in ("", "Markdown", "MarkdownV2", "HTML"):
        errors.append("Invalid parse_mode")
    if settings.telegram.attachment_format not in ("txt", "json", "csv"):
        errors.append("Invalid attachment_format")
    if settings.security.api_key and len(settings.security.api_key.strip()) < 8:
        errors.append("API key must be at least 8 characters long")
    if (
        settings.security.webhook_signing_secret
        and len(settings.security.webhook_signing_secret.strip()) < 8
    ):
        errors.append("Webhook signing secret must be at least 8 characters long")
    if (
        settings.security.openai_api_key
        and not settings.security.openai_api_key.startswith("sk-")
    ):
        errors.append("OpenAI API key must start with 'sk-'")
    if settings.generation.mode not in valid_generation_modes:
        errors.append("Generation mode must be local, openai, gemini or claude")
    if (
        settings.generation.openai_api_key
        and not settings.generation.openai_api_key.startswith("sk-")
    ):
        errors.append("Generation OpenAI API key must start with 'sk-'")
    if settings.generation.temperature < 0 or settings.generation.temperature > 1.5:
        errors.append("Generation temperature must be between 0 and 1.5")
    if settings.generation.max_tokens < 50 or settings.generation.max_tokens > 2000:
        errors.append("Generation max_tokens must be between 50 and 2000")
    if settings.generation.mode == "openai" and not settings.generation.openai_api_key:
        errors.append("OpenAI mode requires an OpenAI API key")
    if settings.generation.mode == "gemini" and not settings.generation.gemini_api_key:
        errors.append("Gemini mode requires a Gemini API key")
    if settings.generation.mode == "claude" and not settings.generation.claude_api_key:
        errors.append("Claude mode requires a Claude API key")
    if not settings.generation.openai_model.strip():
        errors.append("OpenAI model cannot be empty")
    if not settings.generation.gemini_model.strip():
        errors.append("Gemini model cannot be empty")
    if not settings.generation.claude_model.strip():
        errors.append("Claude model cannot be empty")
    if not settings.integrations.redis_url.startswith(("redis://", "rediss://")):
        errors.append("Redis URL must start with redis:// or rediss://")
    if not _is_http_url(settings.integrations.selenium_remote_url):
        errors.append("Selenium remote URL must be a valid HTTP(S) URL")
    if not _is_http_url(settings.integrations.api_url):
        errors.append("API URL must be a valid HTTP(S) URL")
    if not _is_http_url(settings.integrations.api_public_url):
        errors.append("API public URL must be a valid HTTP(S) URL")
    if settings.privacy.job_result_ttl < 60:
        errors.append("job_result_ttl must be at least 60 seconds")
    if settings.privacy.rate_limit_requests < 1:
        errors.append("rate_limit_requests must be at least 1")
    if settings.privacy.rate_limit_window < 1:
        errors.append("rate_limit_window must be at least 1 second")
    if any("://" in domain for domain in settings.privacy.allowed_callback_domains):
        errors.append(
            "allowed_callback_domains must contain domains only, without protocol"
        )
    if not _is_http_url(settings.urls.base_url):
        errors.append("Base URL must be a valid HTTP(S) URL")
    if not _is_http_url(settings.urls.profile_url):
        errors.append("Profile URL must be a valid HTTP(S) URL")
    if not settings.user_profile.display_name.strip():
        errors.append("Display name cannot be empty")
    if not settings.user_profile.username.strip():
        errors.append("Username cannot be empty")
    seen_profiles: set[str] = set()
    for favorite in settings.user_profile.favorite_profiles:
        if not favorite.name.strip():
            errors.append("Favorite profile name cannot be empty")
        if not _is_http_url(favorite.profile_url):
            errors.append("Favorite profile URL must be a valid HTTP(S) URL")
        normalized_url = favorite.profile_url.strip().lower()
        if normalized_url in seen_profiles:
            errors.append("Favorite profiles must not contain duplicate URLs")
        seen_profiles.add(normalized_url)

    return {"valid": len(errors) == 0, "errors": errors}


@app.get(
    "/v1/settings",
    response_model=SettingsResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Settings"],
)
async def get_settings():
    """Get current application settings."""
    try:
        config = _load_config()
        return SettingsResponse(
            success=True,
            message="Settings retrieved successfully",
            settings=_config_to_settings_model(config),
        )
    except Exception as exc:
        return SettingsResponse(
            success=False,
            message=f"Failed to get settings: {exc}",
            settings=None,
        )


@app.put(
    "/v1/settings",
    response_model=SettingsResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Settings"],
)
async def update_settings(settings: SettingsModel):
    """Update and persist application settings."""
    try:
        validation = _validate_settings(settings)
        if not validation["valid"]:
            return SettingsResponse(
                success=False,
                message=f"Validation failed: {', '.join(validation['errors'])}",
                settings=None,
            )

        config = _load_config()
        provided_sections = set(settings.model_fields_set)

        if "telegram" in provided_sections:
            config.telegram.enabled = settings.telegram.enabled
            config.telegram.token = settings.telegram.token
            config.telegram.chat_id = settings.telegram.chat_id
            config.telegram.parse_mode = settings.telegram.parse_mode
            config.telegram.attach_responses_auto = (
                settings.telegram.attach_responses_auto
            )
            config.telegram.attachment_format = settings.telegram.attachment_format

        if "scraping" in provided_sections:
            config.scraping.headless = settings.scraping.headless
            config.scraping.timeout = settings.scraping.timeout
            config.scraping.delay_min = settings.scraping.delay_min
            config.scraping.delay_max = settings.scraping.delay_max
            config.scraping.max_retries = settings.scraping.max_retries
            config.scraping.page_load_timeout = settings.scraping.page_load_timeout
            config.scraping.implicit_wait = settings.scraping.implicit_wait
            config.scraping.explicit_wait = settings.scraping.explicit_wait

        if "delays" in provided_sections:
            config.delays.human_like_min = settings.delays.human_like_min
            config.delays.human_like_max = settings.delays.human_like_max
            config.delays.retry_base = settings.delays.retry_base
            config.delays.error_recovery = settings.delays.error_recovery
            config.delays.rate_limit_retry = settings.delays.rate_limit_retry
            config.delays.page_load_retry = settings.delays.page_load_retry

        if "api" in provided_sections:
            config.api.host = settings.api.host
            config.api.port = settings.api.port
            config.api.debug = settings.api.debug
            config.api.workers = settings.api.workers

        if "security" in provided_sections:
            config.security.api_key = settings.security.api_key
            config.security.webhook_signing_secret = (
                settings.security.webhook_signing_secret
            )
            config.security.openai_api_key = settings.security.openai_api_key

        if "generation" in provided_sections:
            config.generation.mode = settings.generation.mode
            config.generation.openai_api_key = settings.generation.openai_api_key
            config.generation.openai_model = settings.generation.openai_model
            config.generation.gemini_api_key = settings.generation.gemini_api_key
            config.generation.gemini_model = settings.generation.gemini_model
            config.generation.claude_api_key = settings.generation.claude_api_key
            config.generation.claude_model = settings.generation.claude_model
            config.generation.temperature = settings.generation.temperature
            config.generation.max_tokens = settings.generation.max_tokens
            config.generation.system_prompt = settings.generation.system_prompt
            # Keep legacy field in sync for backward compatibility.
            config.security.openai_api_key = settings.generation.openai_api_key

        if "integrations" in provided_sections:
            config.integrations.redis_url = settings.integrations.redis_url
            config.integrations.selenium_remote_url = (
                settings.integrations.selenium_remote_url
            )
            config.integrations.api_url = settings.integrations.api_url
            config.integrations.api_public_url = settings.integrations.api_public_url

        if "privacy" in provided_sections:
            config.privacy.mask_pii = settings.privacy.mask_pii
            config.privacy.id_salt = settings.privacy.id_salt
            config.privacy.job_result_ttl = settings.privacy.job_result_ttl
            config.privacy.rate_limit_requests = settings.privacy.rate_limit_requests
            config.privacy.rate_limit_window = settings.privacy.rate_limit_window
            config.privacy.require_tls_callbacks = (
                settings.privacy.require_tls_callbacks
            )
            config.privacy.allowed_callback_domains = [
                domain.strip()
                for domain in settings.privacy.allowed_callback_domains
                if domain.strip()
            ]

        if "urls" in provided_sections:
            config.urls.base_url = settings.urls.base_url
            config.urls.profile_url = settings.urls.profile_url

        if "user_profile" in provided_sections:
            from config.settings import FavoriteProfileConfig

            config.user_profile.display_name = settings.user_profile.display_name
            config.user_profile.username = settings.user_profile.username
            config.user_profile.favorite_profiles = [
                FavoriteProfileConfig(
                    name=favorite.name.strip(),
                    profile_url=favorite.profile_url.strip(),
                    specialty=favorite.specialty,
                    notes=favorite.notes,
                )
                for favorite in settings.user_profile.favorite_profiles
            ]

        config.save()

        return SettingsResponse(
            success=True,
            message="Settings updated successfully. Restart required for some changes to take effect.",
            settings=_config_to_settings_model(config),
        )
    except Exception as exc:
        return SettingsResponse(
            success=False,
            message=f"Failed to update settings: {exc}",
            settings=None,
        )


@app.post(
    "/v1/settings/validate",
    response_model=SettingsResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Settings"],
)
async def validate_settings_endpoint(settings: SettingsModel):
    """Validate settings without saving."""
    validation = _validate_settings(settings)
    if validation["valid"]:
        return SettingsResponse(
            success=True,
            message="Settings are valid",
            settings=settings,
        )
    return SettingsResponse(
        success=False,
        message=f"Validation failed: {', '.join(validation['errors'])}",
        settings=None,
    )
