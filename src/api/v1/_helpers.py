"""Shared helper functions for API routers and middleware."""

import logging
from typing import NoReturn, Optional

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def raise_public_http_error(
    status_code: int,
    public_message: str,
    *,
    exc: Optional[Exception] = None,
) -> NoReturn:
    """Raise an HTTP error with a safe public message and optional private log."""
    if exc is not None:
        logger.error(
            public_message,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
    raise HTTPException(status_code=status_code, detail=public_message) from None


def http_error_code(status_code: int) -> str:
    return {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
    }.get(status_code, "HTTP_ERROR")
