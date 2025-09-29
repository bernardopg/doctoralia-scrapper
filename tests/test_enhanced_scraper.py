from unittest.mock import MagicMock

import pytest

from src.enhanced_scraper import EnhancedDoctoraliaScraper
from src.error_handling import PageNotFoundError, RateLimitError, ScrapingError
from tests.fixtures import MockConfig


@pytest.fixture
def enhanced_scraper():
    config = MockConfig()
    logger = MagicMock()
    return EnhancedDoctoraliaScraper(config, logger)


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
    def raise_error(_):  # noqa: D401
        raise Exception(message)

    # Force underlying protected function to raise error
    enhanced_scraper.scrape_reviews = MagicMock(side_effect=raise_error)  # type: ignore

    with pytest.raises(expected):
        enhanced_scraper.scrape_page_with_protection(
            "https://www.doctoralia.com.br/test"
        )


def test_get_circuit_status(enhanced_scraper):
    status = enhanced_scraper.get_circuit_status()
    assert "page_load" in status and "api" in status
    assert {"state", "failure_count"}.issubset(status["page_load"].keys())
