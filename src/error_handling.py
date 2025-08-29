"""
Sistema de tratamento de erros melhorado
"""

import functools
import logging
from enum import Enum
from typing import Any, Callable, Optional


class ErrorSeverity(Enum):
    """Níveis de severidade de erro"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScrapingError(Exception):
    """Erro base para scraping"""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        retryable: bool = True,
        context: Optional[dict] = None,
    ):
        super().__init__(message)
        self.severity = severity
        self.retryable = retryable
        self.context = context or {}


class RateLimitError(ScrapingError):
    """Erro de rate limiting"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            f"Rate limit exceeded, retry after {retry_after}s",
            severity=ErrorSeverity.MEDIUM,
            retryable=True,
            context={"retry_after": retry_after},
        )


class PageNotFoundError(ScrapingError):
    """Página não encontrada"""

    def __init__(self, url: str):
        super().__init__(
            f"Page not found: {url}",
            severity=ErrorSeverity.LOW,
            retryable=False,
            context={"url": url},
        )


def retry_with_backoff(
    max_retries: int = 3, backoff_factor: float = 2.0, exceptions: tuple = (Exception,)
):
    """Decorator para retry com backoff exponencial"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    # Se não é retryable, falha imediatamente
                    if hasattr(e, "retryable") and not e.retryable:
                        raise

                    if attempt < max_retries:
                        wait_time = backoff_factor**attempt
                        logging.warning(
                            f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}"
                        )
                        import time

                        time.sleep(wait_time)
                    else:
                        logging.error(f"All {max_retries + 1} attempts failed")

            raise last_exception  # type: ignore

        return wrapper

    return decorator


class ErrorReporter:
    """Reporter de erros para telemetria"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def report_error(self, error: Exception, context: dict = None):
        """Reporta erro com contexto"""
        context = context or {}

        if isinstance(error, ScrapingError):
            self.logger.error(
                f"ScrapingError: {error}",
                extra={
                    "severity": error.severity.value,
                    "retryable": error.retryable,
                    "context": {**error.context, **context},
                },
            )
        else:
            self.logger.error(
                f"Unexpected error: {error}", extra={"context": context}, exc_info=True
            )

    def report_success(self, operation: str, context: dict = None):
        """Reporta sucesso de operação"""
        self.logger.info(
            f"Operation succeeded: {operation}", extra={"context": context or {}}
        )


# Exemplo de uso nos scrapers
@retry_with_backoff(max_retries=3, exceptions=(RateLimitError,))
def scrape_with_retry(url: str, scraper):
    """Scraping com retry automático"""
    try:
        return scraper.scrape_page(url)
    except Exception as e:
        # Transforma exceções genéricas em ScrapingErrors
        if "rate limit" in str(e).lower():
            raise RateLimitError()
        elif "404" in str(e):
            raise PageNotFoundError(url)
        else:
            raise ScrapingError(
                f"Failed to scrape {url}: {e}", severity=ErrorSeverity.HIGH
            )
