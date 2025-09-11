"""
Main API module for n8n integration.
"""

import os
import time
import uuid
from datetime import datetime
from typing import Optional

import redis
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rq import Queue

from src.api.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
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
from src.integrations.n8n.normalize import (
    extract_scraper_result,
    make_unified_result,
)
from src.jobs.queue import get_queue
from src.jobs.tasks import scrape_and_process

# API metadata
API_VERSION = "1.0.0"
API_START_TIME = datetime.now()

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


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    
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
    """Readiness check endpoint."""
    checks = {}
    
    # Check Redis
    try:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False
    
    # Check Selenium (optional for readiness)
    checks["selenium"] = True  # Assume available for now
    
    ready = all(checks.values())
    
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready",
        )
    
    return ReadyResponse(ready=ready, checks=checks)


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
        from src.scraper import DoctoraliaScraper
        
        # Initialize scraper
        scraper = DoctoraliaScraper()
        
        # Run scraping
        scraper_result = scraper.scrape_doctor_reviews(str(request.doctor_url))
        
        # Extract data
        doctor_data, reviews_data = extract_scraper_result(scraper_result)
        
        # Run analysis if requested
        analysis_data = None
        if request.include_analysis:
            from src.response_quality_analyzer import ResponseQualityAnalyzer
            
            analyzer = ResponseQualityAnalyzer()
            # Analyze all reviews
            sentiments = []
            for review in reviews_data:
                sentiment = analyzer.analyze_sentiment(review.get("comment", ""))
                sentiments.append(sentiment)
            
            # Aggregate sentiment
            if sentiments:
                avg_sentiment = {
                    "compound": sum(s["compound"] for s in sentiments) / len(sentiments),
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
            
            generator = ResponseGenerator()
            responses = []
            
            for idx, review in enumerate(reviews_data):
                response_text = generator.generate_response(
                    review.get("comment", ""),
                    template_id=request.response_template_id,
                    language=request.language,
                )
                responses.append({
                    "review_id": str(idx),
                    "text": response_text,
                    "language": request.language or "pt",
                })
            
            generation_data = {
                "template_id": request.response_template_id,
                "responses": responses,
                "model": {"type": "template"},
            }
        
        # Create unified result
        result = make_unified_result(
            doctor_data=doctor_data,
            reviews_data=reviews_data,
            analysis_data=analysis_data,
            generation_data=generation_data,
            status="completed",
            start_time=start_time,
            end_time=datetime.now(),
        )
        
        return result
        
    except Exception as e:
        # Create error result
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
async def create_job(request: JobCreateRequest, idem_key: Optional[str] = None):
    """
    Create an async scraping job.
    Returns job ID for polling.
    """
    # Get or create job ID
    if idem_key:
        # Check for existing job with this idempotency key
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        existing_job_id = r.get(f"idem:{idem_key}")
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
    job = q.enqueue(
        scrape_and_process,
        request.dict(),
        job_id,
        str(request.callback_url) if request.callback_url else None,
        job_id=job_id,
    )
    
    # Store idempotency key if provided
    if idem_key:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.setex(f"idem:{idem_key}", 3600, job_id)  # 1 hour TTL
    
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
        status = "running"
    elif job.is_started:
        status = "running"
    elif job.is_finished:
        status = "completed"
    elif job.is_failed:
        status = "failed"
    else:
        status = "unknown"
    
    # Return result if available
    if job.is_finished and job.result:
        return job.result
    
    # Return status placeholder
    return make_unified_result(
        doctor_data={"name": "Processing", "url": ""},
        reviews_data=[],
        job_id=job_id,
        status=status,
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
