"""Exercise pagination failures and completeness through the scraper boundary."""

from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException

from src.scraper import DoctoraliaScraper
from tests.fixtures import MockConfig


def make_scraper():
    scraper = DoctoraliaScraper(MockConfig(), MagicMock())
    scraper.driver = MagicMock()
    scraper.driver.current_url = "https://www.doctoralia.com.br/perfil/exemplo"
    scraper.driver.page_source = """
        <section id="profile-reviews">
          <p class="mb-0">2 opiniões</p>
          <div data-test-id="opinion-block" data-id="123">
            <p data-test-id="opinion-comment">Atendimento excelente</p>
          </div>
        </section>
    """
    scraper.setup_driver = MagicMock(return_value=True)
    scraper.safe_driver_quit = MagicMock()
    scraper.extract_doctor_name = MagicMock(return_value="Dra. Ana")
    scraper.rate_limiter.wait_if_needed = MagicMock()
    scraper.rate_limiter.add_delay = MagicMock()
    scraper.add_human_delay = MagicMock()
    return scraper


def test_scraper_reports_fewer_extracted_than_advertised():
    scraper = make_scraper()
    scraper._find_load_more_button = MagicMock(return_value=None)
    scraper._count_current_reviews = MagicMock(return_value=1)
    with patch("src.scraper.WebDriverWait") as wait:
        wait.return_value.until.return_value = True
        result = scraper._process_single_scrape_attempt(scraper.driver.current_url, 0)
    assert result is not None
    assert result["collection"]["status"] == "partial"
    assert result["collection"]["expected_count"] == 2
    assert result["collection"]["extracted_count"] == 1
    assert result["collection"]["stop_reason"] == "exhausted"
    assert result["reviews"][0]["id"] == "doctoralia:123"


def test_scraper_uses_backup_after_losing_browser_session():
    scraper = make_scraper()
    backup = [{"id": "doctoralia:123", "comment": "Atendimento excelente"}]
    scraper.click_load_more_button = MagicMock(return_value=(3, backup))
    scraper._extract_all_reviews = MagicMock(
        side_effect=WebDriverException("session lost")
    )
    with patch("src.scraper.WebDriverWait") as wait:
        wait.return_value.until.return_value = True
        result = scraper._process_single_scrape_attempt(scraper.driver.current_url, 0)
    assert result is not None
    assert result["reviews"] == backup
    assert result["collection"]["status"] == "partial"
    assert result["collection"]["stop_reason"] == "browser_error"


@pytest.mark.parametrize(
    "reason", ["time_limit", "load_timeout", "browser_error", "click_limit"]
)
def test_pagination_records_why_it_stopped(reason):
    scraper = make_scraper()
    scraper._count_current_reviews = MagicMock(return_value=1)
    scraper._find_load_more_button = MagicMock(return_value=MagicMock())
    if reason == "browser_error":
        scraper.driver.execute_script.side_effect = WebDriverException("disconnected")
    with (
        patch("src.scraper.WebDriverWait") as wait,
        patch("src.scraper.time.time") as clock,
    ):
        clock.return_value = 0
        clock.side_effect = [0, 181] if reason == "time_limit" else None
        if reason == "load_timeout":
            wait.return_value.until.side_effect = TimeoutException("no new reviews")
        scraper.click_load_more_button()
    assert scraper._pagination_stop_reason == reason


def test_pagination_without_driver_is_unavailable():
    scraper = make_scraper()
    scraper.driver = None
    assert scraper.click_load_more_button() == (0, [])
    assert scraper._pagination_stop_reason == "unavailable"


def test_pagination_handles_session_loss_when_counting_final_reviews():
    scraper = make_scraper()
    scraper._find_load_more_button = MagicMock(return_value=None)
    scraper._count_current_reviews = MagicMock(
        side_effect=[1, WebDriverException("lost")]
    )
    scraper.click_load_more_button()
    assert scraper._pagination_stop_reason == "browser_error"
