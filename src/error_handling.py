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


class EnhancedErrorHandler:
    """
    Enhanced error handling with retry logic and detailed logging.
    """

    def __init__(
        self, logger: Optional[logging.Logger] = None, max_retries: int = 3
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.max_retries = max_retries

    def execute_with_retry(
        self, func: Any, *args: Any, operation_name: str = "operation", **kwargs: Any
    ) -> Any:
        """
        Execute a function with retry logic and enhanced error handling.
        """
        import time

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                self.logger.debug(
                    f"Attempting {operation_name} (attempt {attempt + 1}/{self.max_retries})"
                )
                result = func(*args, **kwargs)
                if attempt > 0:
                    self.logger.info(
                        f"{operation_name} succeeded on attempt {attempt + 1}"
                    )
                return result

            except Exception as e:
                last_exception = e
                self.logger.warning(
                    f"Attempt {attempt + 1} failed for {operation_name}: {str(e)}"
                )

                # Don't retry on certain types of errors
                if self._is_fatal_error(e):
                    self.logger.error(
                        f"Fatal error in {operation_name}, not retrying: {str(e)}"
                    )
                    break

                # Wait before retry (exponential backoff)
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt  # 1s, 2s, 4s
                    self.logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)

        # All retries exhausted
        if last_exception:
            error_msg = f"{operation_name} failed after {self.max_retries} attempts: {str(last_exception)}"
            self.logger.error(error_msg)
            raise last_exception
        else:
            error_msg = f"{operation_name} failed after {self.max_retries} attempts: Unknown error"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

    def _is_fatal_error(self, exception: Exception) -> bool:
        """Determine if an error is fatal and shouldn't be retried."""
        fatal_errors = (
            ValueError,  # Invalid input
            TypeError,  # Type errors
            AttributeError,  # Missing attributes
            ImportError,  # Import errors
            KeyboardInterrupt,  # User interruption
        )

        return isinstance(exception, fatal_errors)


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
