"""Contract tests with synthetic data and no external services."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.api.v1.routers.scrape import scrape_run
from src.services.scrape_completeness import ensure_collection, result_status


def test_missing_collection_is_explicitly_unknown():
    payload = {"reviews": []}
    info = ensure_collection(payload)
    assert info == {
        "status": "unknown",
        "expected_count": None,
        "extracted_count": 0,
        "stop_reason": "metadata_unavailable",
        "duration_ms": None,
    }
    assert result_status(info) == "partial"


def test_synchronous_endpoint_keeps_event_loop_responsive():
    started = threading.Event()
    release = threading.Event()
    watchdog = threading.Timer(5, release.set)

    def blocked_scraper(request, config):
        started.set()
        release.wait()
        return "done"

    async def exercise():
        with patch("src.api.v1.routers.scrape._scrape_run", blocked_scraper):
            task = asyncio.create_task(scrape_run(SimpleNamespace(), None))
            assert await asyncio.to_thread(started.wait, 3)
            # The blocked operation must still be waiting when this coroutine runs.
            assert not release.is_set()
            release.set()
            assert await task == "done"

    watchdog.start()
    try:
        asyncio.run(exercise())
    finally:
        release.set()
        watchdog.cancel()


def test_driver_is_closed_if_setup_fails():
    from unittest.mock import MagicMock

    from src.scraper import DoctoraliaScraper

    scraper = DoctoraliaScraper.__new__(DoctoraliaScraper)
    scraper.config = SimpleNamespace(scraping=SimpleNamespace(max_retries=1))
    scraper.logger = MagicMock()
    scraper.driver = MagicMock()
    driver = scraper.driver
    scraper.setup_driver = lambda: False
    assert (
        scraper._process_single_scrape_attempt("https://www.doctoralia.com.br/test", 0)
        is None
    )
    driver.quit.assert_called_once()
    assert scraper.driver is None


def test_worker_and_sync_report_failures(tmp_path):
    from unittest.mock import MagicMock

    from src.api.v1.routers.scrape import _scrape_run
    from src.jobs.tasks import scrape_and_process

    config = MagicMock(data_dir=tmp_path)
    scraper = MagicMock()
    scraper.scrape_reviews.side_effect = TimeoutError("synthetic")
    request = SimpleNamespace(doctor_url="https://www.doctoralia.com.br/test")
    with (
        patch("src.scraper.DoctoraliaScraper", return_value=scraper),
        patch("src.config.settings.AppConfig.load", return_value=config),
    ):
        sync = _scrape_run(request, config).model_dump()
        worker = scrape_and_process({"doctor_url": request.doctor_url})
    for result in (sync, worker):
        assert result["status"] == "failed"
        assert result["collection"]["status"] == "failure"
        assert result["collection"]["stop_reason"] == "TimeoutError"
        assert result["collection"]["duration_ms"] >= 0
    scraper.save_data.assert_not_called()


def test_sync_snapshot_is_visible_in_workspace(tmp_path):
    import json
    from unittest.mock import MagicMock

    from src.api.v1.routers.scrape import _scrape_run
    from src.services.workspace_service import WorkspaceService

    url = "https://www.doctoralia.com.br/test"
    config = MagicMock(data_dir=tmp_path)
    scraper = MagicMock()
    scraper.scrape_reviews.return_value = {
        "doctor_name": "Test",
        "url": url,
        "reviews": [],
        "collection": {
            "status": "complete",
            "expected_count": 0,
            "extracted_count": 0,
            "stop_reason": "exhausted",
            "duration_ms": 1,
        },
    }

    def save(payload):
        path = tmp_path / "snapshot.json"
        path.write_text(json.dumps(payload))
        return path

    scraper.save_data.side_effect = save
    request = SimpleNamespace(
        doctor_url=url, include_analysis=False, include_generation=False
    )
    with patch("src.scraper.DoctoraliaScraper", return_value=scraper):
        result = _scrape_run(request, config)
    assert result.status == "completed"
    overview = WorkspaceService(tmp_path, MagicMock()).get_overview()
    assert overview["recent_scrapes"][0]["collection"]["status"] == "complete"


@pytest.mark.parametrize("execution", ["sync", "worker"])
@pytest.mark.parametrize("newer_draft", ["Recent edit", "", None])
def test_draft_authority_uses_chronology_including_partial_snapshots(
    tmp_path, execution, newer_draft
):
    import json
    from unittest.mock import MagicMock

    from src.api.v1.routers.scrape import _scrape_run
    from src.jobs.tasks import scrape_and_process

    url = "https://www.doctoralia.com.br/test"
    review = {"id": "doctoralia:42", "author": "Test", "comment": "Review"}
    for name, timestamp, status, draft in (
        ("complete.json", "2026-01-01T12:00:00Z", "complete", "Old edit"),
        ("partial.json", "2026-01-02T12:00:00Z", "partial", newer_draft),
    ):
        previous = dict(review)
        if draft is not None:
            previous["generated_response"] = draft
        (tmp_path / name).write_text(
            json.dumps(
                {
                    "url": url,
                    "doctor_name": "Test",
                    "extraction_timestamp": timestamp,
                    "collection": {"status": status},
                    "reviews": [previous],
                }
            ),
            encoding="utf-8",
        )
    config = SimpleNamespace(data_dir=tmp_path)
    scraper = MagicMock()
    scraper.scrape_reviews.return_value = {
        "url": url,
        "doctor_name": "Test",
        "extraction_timestamp": "2026-01-03T12:00:00Z",
        "collection": {"status": "complete"},
        "reviews": [review],
    }

    def save(payload):
        target = tmp_path / "new.json"
        target.write_text(json.dumps(payload), encoding="utf-8")
        return target

    scraper.save_data.side_effect = save
    with (
        patch("src.scraper.DoctoraliaScraper", return_value=scraper),
        patch("src.config.settings.AppConfig.load", return_value=config),
    ):
        if execution == "sync":
            result = _scrape_run(
                SimpleNamespace(
                    doctor_url=url, include_analysis=False, include_generation=False
                ),
                config,
            ).model_dump()
        else:
            result = scrape_and_process({"doctor_url": url})
    assert result["status"] == "completed"
    expected = newer_draft or None
    assert result["reviews"][0]["metadata"].get("generated_response") == expected
    saved = json.loads((tmp_path / "new.json").read_text(encoding="utf-8"))
    assert saved["reviews"][0].get("generated_response") == expected
