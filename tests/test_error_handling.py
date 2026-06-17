import logging

import pytest
from selenium.common.exceptions import (
    InvalidSelectorException,
    NoSuchElementException,
    SessionNotCreatedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

from src.error_handling import (
    EnhancedErrorHandler,
    ErrorReporter,
    PageNotFoundError,
    RateLimitError,
    ScrapingError,
    retry_with_backoff,
)


def test_rate_limit_error_properties():
    err = RateLimitError(retry_after=15)
    assert err.retryable is True
    assert err.context["retry_after"] == 15


def test_page_not_found_not_retryable():
    err = PageNotFoundError("https://example.com/404")
    assert err.retryable is False
    assert err.context["url"].endswith("404")


def test_retry_with_backoff_success_after_retry(monkeypatch):
    calls = {"n": 0}
    sleep_calls = []

    def fake_sleep(t):  # noqa: D401
        sleep_calls.append(t)

    monkeypatch.setattr("time.sleep", fake_sleep)

    @retry_with_backoff(max_retries=2, backoff_factor=1, exceptions=(RateLimitError,))
    def flaky():
        if calls["n"] == 0:
            calls["n"] += 1
            raise RateLimitError(1)
        return "done"

    assert flaky() == "done"
    assert sleep_calls  # At least one backoff call recorded


def test_retry_with_backoff_exhausts(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)

    @retry_with_backoff(max_retries=1, backoff_factor=0, exceptions=(RateLimitError,))
    def always_fail():
        raise RateLimitError(1)

    with pytest.raises(RateLimitError):
        always_fail()


def test_error_reporter_logs_scraping_error(caplog):
    logger = logging.getLogger("test_error_reporter.scraping")
    reporter = ErrorReporter(logger=logger)
    err = ScrapingError("failed", retryable=True, context={"x": 1})
    with caplog.at_level("ERROR"):
        reporter.report_error(err, {"y": 2})
    assert any("ScrapingError" in r.message for r in caplog.records)


def test_error_reporter_logs_unexpected_error(caplog):
    logger = logging.getLogger("test_error_reporter.unexpected")
    reporter = ErrorReporter(logger=logger)
    with caplog.at_level("ERROR"):
        reporter.report_error(ValueError("boom"), {"op": "t"})
    assert any("Unexpected" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# EnhancedErrorHandler._is_fatal_error
# ---------------------------------------------------------------------------


@pytest.fixture
def handler():
    return EnhancedErrorHandler(logger=logging.getLogger("test_is_fatal"))


def test_is_fatal_honours_scraping_error_retryable(handler):
    # Non-retryable domain error is fatal; retryable is not.
    assert handler._is_fatal_error(PageNotFoundError("https://x/404")) is True
    assert handler._is_fatal_error(RateLimitError(retry_after=5)) is False
    assert handler._is_fatal_error(ScrapingError("x", retryable=True)) is False
    assert handler._is_fatal_error(ScrapingError("x", retryable=False)) is True


def test_is_fatal_selenium_broken_selector_is_fatal(handler):
    # Broken selector / config errors won't be fixed by retrying.
    assert handler._is_fatal_error(NoSuchElementException()) is True
    assert handler._is_fatal_error(InvalidSelectorException()) is True
    assert handler._is_fatal_error(SessionNotCreatedException()) is True


def test_is_fatal_selenium_transient_is_not_fatal(handler):
    # Transient Selenium failures should be retried.
    assert handler._is_fatal_error(TimeoutException()) is False
    assert handler._is_fatal_error(StaleElementReferenceException()) is False
    assert handler._is_fatal_error(WebDriverException()) is False


def test_is_fatal_generic_programming_errors(handler):
    assert handler._is_fatal_error(ValueError("bad")) is True
    assert handler._is_fatal_error(TypeError("bad")) is True
    # A plain transient-looking error with no special handling is not fatal.
    assert handler._is_fatal_error(RuntimeError("transient")) is False
