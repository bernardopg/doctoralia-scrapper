"""
Main API module for n8n integration.
"""

import os
import time
import uuid
from datetime import datetime
from typing import Optional  # noqa: F401 (kept for future extensibility)

import redis
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    ReadyComponent,
    ReadyResponse,
    UnifiedResult,
)
from src.api.schemas.requests import (
    JobCreateRequest,
    JobResponse,
    ScrapeRequest,
    WebhookRequest,
    WebhookResponse,
)
from src.api.v1.deps import require_api_key, verify_webhook_signature
from src.integrations.n8n.normalize import extract_scraper_result, make_unified_result
from src.jobs.queue import get_queue
from src.jobs.tasks import scrape_and_process

# API metadata
API_VERSION = "1.0.0"
API_START_TIME = datetime.now()

# In-memory (process local) metrics - simple lightweight instrumentation.
# For multi-process deployment, replace with Prometheus client or Redis aggregation.
METRICS = {
    "requests_total": 0,
    "requests_in_progress": 0,
    "requests_failed_total": 0,
    "scrapes_total": 0,
    "scrapes_failed_total": 0,
    "generation_total": 0,
    "analysis_total": 0,
    "request_durations_ms": [],  # store last N durations (trimmed) for p95/p99
}
METRICS_MAX_SAMPLES = 500

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


def start_api(
    host: str = "0.0.0.0", port: int = 8000
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


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID, collect basic metrics, and structured timing headers."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.perf_counter()
    METRICS["requests_total"] += 1
    METRICS["requests_in_progress"] += 1
    try:
        response = await call_next(request)
    except Exception:
        METRICS["requests_failed_total"] += 1
        raise
    finally:
        METRICS["requests_in_progress"] -= 1
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    # Keep rolling sample
    METRICS["request_durations_ms"].append(duration_ms)
    if len(METRICS["request_durations_ms"]) > METRICS_MAX_SAMPLES:
        METRICS["request_durations_ms"] = METRICS["request_durations_ms"][
            -METRICS_MAX_SAMPLES:
        ]
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
                details=str(exc) if os.getenv("DEBUG") else None,
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

    # Redis connectivity & latency
    redis_ok = False
    redis_error = None
    redis_latency = None
    try:
        start = time.perf_counter()
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
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
    templates_dir = os.path.join(os.getcwd(), "config", "templates")
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

    # Selenium placeholder (could attempt driver check with timeout)
    components["selenium"] = ReadyComponent(
        status=True, latency_ms=None, error=None, details=None
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
                    response_text = generator.generate_response(review)
                except Exception:
                    response_text = ""
                responses.append(
                    {
                        "review_id": str(review.get("id", idx)),
                        "text": response_text,
                        "language": request.language or "pt",
                    }
                )
            generation_data = {
                "template_id": request.response_template_id,
                "responses": responses,
                "model": {"type": "rule-based"},
            }

        # Create unified result and return
        METRICS["scrapes_total"] += 1
        if request.include_analysis:
            METRICS["analysis_total"] += 1
        if request.include_generation:
            METRICS["generation_total"] += 1
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
        METRICS["scrapes_failed_total"] += 1
        return make_unified_result(
            doctor_data={"name": "Error", "url": str(request.doctor_url)},
            reviews_data=[],
            status="failed",
            start_time=start_time,
            end_time=datetime.now(),
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
    if request.idempotency_key:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        existing_job_id = r.get(f"idem:{request.idempotency_key}")
        if existing_job_id:
            return JobResponse(
                job_id=existing_job_id.decode(),
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
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.setex(f"idem:{request.idempotency_key}", 3600, job_id)

    return JobResponse(
        job_id=job_id,
        status="queued",
        message="Job created successfully",
    )


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
    if job.is_queued or job.is_deferred:
        job_status = "running"
    elif job.is_started:
        job_status = "running"
    elif job.is_finished:
        job_status = "completed"
    elif job.is_failed:
        job_status = "failed"
    else:
        job_status = "unknown"

    # Return result if available
    if job.is_finished and job.result:
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
    """Return basic process-level metrics (NOT Prometheus format)."""
    durations = METRICS["request_durations_ms"]
    body = {
        "version": API_VERSION,
        "uptime_s": int((datetime.now() - API_START_TIME).total_seconds()),
        "requests": {
            "total": METRICS["requests_total"],
            "in_progress": METRICS["requests_in_progress"],
            "failed": METRICS["requests_failed_total"],
            "p50_ms": _percentile(durations, 0.50),
            "p95_ms": _percentile(durations, 0.95),
            "p99_ms": _percentile(durations, 0.99),
            "latest_ms": durations[-1] if durations else None,
            "sample_size": len(durations),
        },
        "scraping": {
            "scrapes_total": METRICS["scrapes_total"],
            "scrapes_failed_total": METRICS["scrapes_failed_total"],
            "analysis_total": METRICS["analysis_total"],
            "generation_total": METRICS["generation_total"],
        },
    }
    return body
