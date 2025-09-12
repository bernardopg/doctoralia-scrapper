import logging

import pytest

from src.error_handling import (
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
