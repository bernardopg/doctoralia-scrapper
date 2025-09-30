from unittest.mock import MagicMock

import pytest

from src.enhanced_scraper import EnhancedDoctoraliaScraper
from src.error_handling import PageNotFoundError, RateLimitError, ScrapingError
from tests.fixtures import MockConfig


@pytest.fixture
def enhanced_scraper():
    """Create a fresh EnhancedDoctoraliaScraper instance for each test"""
    config = MockConfig()
    logger = MagicMock()
    scraper = EnhancedDoctoraliaScraper(config, logger)
    # Ensure circuit breaker is in clean state
    scraper.page_load_circuit.reset()
    scraper.api_circuit.reset()
    return scraper


def test_scrape_page_with_protection_success(enhanced_scraper):
    # Mock internal scrape_reviews to return dummy data
    enhanced_scraper.scrape_reviews = MagicMock(
        return_value={"reviews": [], "total_reviews": 0}
    )  # type: ignore
    data = enhanced_scraper.scrape_page_with_protection(
        "https://www.doctoralia.com.br/test"
    )
    assert isinstance(data, dict)
    enhanced_scraper.scrape_reviews.assert_called_once()


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Rate limit exceeded", RateLimitError),
        ("404 Not Found", PageNotFoundError),
        ("Some other error", ScrapingError),
    ],
)
def test_scrape_page_with_protection_error_mapping(enhanced_scraper, message, expected):
    # Reset circuit breaker state and increase threshold to allow multiple retries
    # without triggering the circuit breaker (retry_with_backoff does 3 retries)
    enhanced_scraper.page_load_circuit.reset()
    enhanced_scraper.page_load_circuit.failure_threshold = 10

    def raise_error(_):  # noqa: D401
        raise Exception(message)

    # Mock _scrape_page_protected directly to avoid multiple failures from retry logic
    # triggering the circuit breaker
    enhanced_scraper._scrape_page_protected = MagicMock(side_effect=raise_error)  # type: ignore

    with pytest.raises(expected):
        enhanced_scraper.scrape_page_with_protection(
            "https://www.doctoralia.com.br/test"
        )


def test_get_circuit_status(enhanced_scraper):
    status = enhanced_scraper.get_circuit_status()
    assert "page_load" in status and "api" in status
    assert {"state", "failure_count"}.issubset(status["page_load"].keys())
