"""HTTP middleware and exception handler registration for the API."""

import ipaddress
import logging
import os
import time
import uuid
from typing import Optional

import redis
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.api.schemas.common import ErrorDetail, ErrorResponse
from src.api.v1._helpers import http_error_code
from src.api.v1._state import (
    RATE_LIMIT_PREFIX,
    is_debug_enabled,
    load_config,
    record_request_end_metric,
    record_request_start_metric,
)

logger = logging.getLogger(__name__)


def _rate_limit_identifier(request: Request) -> str:
    presented_key = request.headers.get("X-API-Key") or request.query_params.get(
        "api_key"
    )
    if presented_key:
        return "key:supplied"

    forwarded_for = request.headers.get("X-Forwarded-For", "")
    client_ip = forwarded_for.split(",", 1)[0].strip()
    if not client_ip and request.client:
        client_ip = request.client.host
    return f"ip:{client_ip or 'unknown'}"


def _is_private_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def _is_rate_limit_exempt(request: Request) -> bool:
    path = request.url.path
    if path in {"/", "/v1/health", "/v1/ready", "/v1/version"} or path.startswith(
        ("/docs", "/redoc", "/openapi.json")
    ):
        return True

    forwarded_for = request.headers.get("X-Forwarded-For", "")
    client_ip = forwarded_for.split(",", 1)[0].strip()
    if not client_ip and request.client:
        client_ip = request.client.host
    return bool(client_ip and _is_private_ip(client_ip))


def _check_rate_limit(request: Request) -> Optional[JSONResponse]:
    if _is_rate_limit_exempt(request):
        return None
    if os.getenv("PYTEST_CURRENT_TEST"):
        return None

    try:
        config = load_config()
        max_requests = int(config.privacy.rate_limit_requests)
        window = int(config.privacy.rate_limit_window)
        if max_requests <= 0 or window <= 0:
            return None

        redis_client = redis.Redis.from_url(config.integrations.redis_url)
        identifier = _rate_limit_identifier(request)
        bucket = int(time.time() // window)
        key = f"{RATE_LIMIT_PREFIX}:{identifier}:{bucket}"
        count: int = redis_client.incr(key)  # type: ignore[assignment]
        if count == 1:
            redis_client.expire(key, window + 5)

        remaining = max(max_requests - count, 0)
        if count <= max_requests:
            request.state.rate_limit_remaining = remaining
            return None

        retry_after = window - (int(time.time()) % window)
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(max(1, retry_after))},
            content=ErrorResponse(
                error=ErrorDetail(
                    code="RATE_LIMITED",
                    message="Rate limit exceeded",
                    details={"window_seconds": window, "limit": max_requests},
                    request_id=getattr(request.state, "request_id", None),
                )
            ).model_dump(),
        )
    except Exception as exc:  # pragma: no cover - redis/config dependent
        logger.debug("Rate limit check skipped: %s", exc)
        return None


def register_api_middleware(app: FastAPI) -> None:
    """Register request middleware and API-wide exception handlers."""

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        started_at_s = time.time()
        start_time = time.perf_counter()
        failed = False
        record_request_start_metric(request_id, started_at_s)

        try:
            rate_limited_response = _check_rate_limit(request)
            if rate_limited_response is not None:
                failed = True
                response = rate_limited_response
            else:
                response = await call_next(request)
        except Exception:
            failed = True
            raise
        finally:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            record_request_end_metric(request_id, duration_ms, failed=failed)

        response.headers["X-Request-Id"] = request_id
        response.headers["X-Response-Time-ms"] = str(duration_ms)
        if hasattr(request.state, "rate_limit_remaining"):
            response.headers["X-RateLimit-Remaining"] = str(
                request.state.rate_limit_remaining
            )
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        status_code = exc.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR
        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=http_error_code(status_code),
                    message=str(exc.detail),
                    details=None,
                    request_id=getattr(request.state, "request_id", None),
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An internal error occurred",
                    details=str(exc) if is_debug_enabled() else None,
                    request_id=getattr(request.state, "request_id", None),
                )
            ).model_dump(),
        )
