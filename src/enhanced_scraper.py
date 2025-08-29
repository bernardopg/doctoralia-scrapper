"""
Sistema de scraping com circuit breaker e error handling melhorado
"""

import logging
from typing import Any, Dict, Optional

from .circuit_breaker import CircuitBreaker
from .error_handling import (
    ErrorReporter,
    PageNotFoundError,
    RateLimitError,
    ScrapingError,
    retry_with_backoff,
)
from .scraper import DoctoraliaScraper


class EnhancedDoctoraliaScraper(DoctoraliaScraper):
    """
    Scraper melhorado com circuit breaker e error handling avançado
    """

    def __init__(
        self,
        config: Any,
        logger: Optional[logging.Logger] = None,
        performance_monitor: Optional[Any] = None,
        error_handler: Optional[Any] = None,
    ):
        super().__init__(config, logger, performance_monitor, error_handler)

        # Circuit breakers para diferentes operações
        self.page_load_circuit = CircuitBreaker(
            failure_threshold=3, recovery_timeout=30.0, expected_exception=Exception
        )

        self.api_circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

        # Error reporter
        self.error_reporter = ErrorReporter(self.logger)

    @retry_with_backoff(max_retries=3, exceptions=(RateLimitError,))
    def scrape_page_with_protection(self, url: str) -> Dict[str, Any]:
        """Scraping com proteção de circuit breaker e retry"""
        try:
            return self.page_load_circuit(self._scrape_page_protected)(url)
        except Exception as e:
            # Transformar exceções genéricas em ScrapingErrors específicos
            if "rate limit" in str(e).lower():
                raise RateLimitError()
            elif "404" in str(e) or "not found" in str(e).lower():
                raise PageNotFoundError(url)
            else:
                raise ScrapingError(
                    f"Failed to scrape {url}: {e}", retryable=True, context={"url": url}
                )

    def _scrape_page_protected(self, url: str) -> Dict[str, Any]:
        """Scraping protegido por circuit breaker"""
        try:
            result = self.scrape_reviews(url)
            if result is None:
                raise ScrapingError(f"No data returned for {url}")
            self.error_reporter.report_success("page_scrape", {"url": url})
            return result
        except Exception as e:
            self.error_reporter.report_error(e, {"url": url})
            raise

    def get_circuit_status(self) -> Dict[str, Dict]:
        """Retorna status dos circuit breakers"""
        return {
            "page_load": self.page_load_circuit.status,
            "api": self.api_circuit.status,
        }
