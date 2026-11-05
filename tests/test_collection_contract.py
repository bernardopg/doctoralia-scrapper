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

    from src.scraper import BrowserSetupError, DoctoraliaScraper

    scraper = DoctoraliaScraper.__new__(DoctoraliaScraper)
    scraper.config = SimpleNamespace(scraping=SimpleNamespace(max_retries=1))
    scraper.logger = MagicMock()
    scraper.driver = MagicMock()
    driver = scraper.driver
    scraper.setup_driver = lambda: False
    with pytest.raises(BrowserSetupError):
        scraper._process_single_scrape_attempt("https://www.doctoralia.com.br/test", 0)
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

    from src.scraper import DoctoraliaScraper

    real = DoctoraliaScraper.__new__(DoctoraliaScraper)
    real.config = config
    real.logger = MagicMock()
    scraper.save_data.side_effect = lambda payload: real.save_data(payload)

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
    saved_path = next(
        p
        for p in tmp_path.glob("*.json")
        if p.name not in {"complete.json", "partial.json"}
    )
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    assert saved["reviews"][0].get("generated_response") == expected


@pytest.mark.parametrize("error_name", ["TimeoutException", "WebDriverException"])
@pytest.mark.parametrize("execution", ["sync", "worker"])
def test_real_attempt_preserves_selenium_error_after_retries(
    tmp_path, error_name, execution
):
    from contextlib import nullcontext
    from unittest.mock import MagicMock

    from selenium.common import exceptions

    from src.api.v1.routers.scrape import _scrape_run
    from src.jobs.tasks import scrape_and_process
    from src.scraper import DoctoraliaScraper

    config = MagicMock(data_dir=tmp_path)
    config.scraping.max_retries = 2
    config.scraping.explicit_wait = 1
    config.delays.error_recovery = 0
    scraper = DoctoraliaScraper.__new__(DoctoraliaScraper)
    scraper.config = config
    scraper.logger = MagicMock()
    scraper.driver = None
    scraper.rate_limiter = MagicMock()
    scraper.progress_callback = None
    scraper.performance_monitor = MagicMock()
    scraper.performance_monitor.track_operation.return_value = nullcontext(MagicMock())
    drivers = []

    def setup():
        driver = MagicMock()
        if error_name == "WebDriverException":
            driver.get.side_effect = getattr(exceptions, error_name)(
                "secret synthetic message"
            )
        drivers.append(driver)
        scraper.driver = driver
        return True

    scraper.setup_driver = setup
    url = "https://www.doctoralia.com.br/synthetic"
    error = getattr(exceptions, error_name)("secret synthetic message")
    with (
        patch("src.scraper.DoctoraliaScraper", return_value=scraper),
        patch("src.config.settings.AppConfig.load", return_value=config),
        patch("src.scraper.WebDriverWait") as wait,
        patch("src.jobs.tasks._update_job_meta") as metadata,
    ):
        wait.return_value.until.side_effect = error
        if execution == "sync":
            result = _scrape_run(SimpleNamespace(doctor_url=url), config).model_dump()
        else:
            result = scrape_and_process({"doctor_url": url})
    assert result["status"] == "failed"
    assert result["collection"]["stop_reason"] == error_name
    assert result["collection"]["duration_ms"] >= 0
    assert "secret synthetic message" not in str(result)
    assert "secret synthetic message" not in str(metadata.call_args_list)
    assert len(drivers) == 2
    for driver in drivers:
        driver.get.assert_called_once_with(url)
        driver.quit.assert_called_once()


@pytest.mark.parametrize(
    "error_name", ["SessionNotCreatedException", "WebDriverException"]
)
@pytest.mark.parametrize("execution", ["sync", "worker"])
def test_setup_failures_close_each_driver_and_report_safe_cause(
    tmp_path, error_name, execution
):
    from contextlib import nullcontext
    from unittest.mock import MagicMock

    from selenium.common import exceptions

    from src.api.v1.routers.scrape import _scrape_run
    from src.jobs.tasks import scrape_and_process
    from src.scraper import DoctoraliaScraper

    config = MagicMock(data_dir=tmp_path)
    config.scraping.max_retries = 2
    config.delays.retry_base = 0
    config.delays.error_recovery = 0
    config.integrations.selenium_remote_url = "http://synthetic.invalid"
    scraper = DoctoraliaScraper.__new__(DoctoraliaScraper)
    scraper.config = config
    scraper.logger = MagicMock()
    scraper.driver = None
    scraper.performance_monitor = MagicMock()
    scraper.performance_monitor.track_operation.return_value = nullcontext(MagicMock())
    drivers = []

    def remote(**kwargs):
        driver = MagicMock()
        driver.set_page_load_timeout.side_effect = getattr(exceptions, error_name)(
            "secret"
        )
        drivers.append(driver)
        return driver

    url = "https://www.doctoralia.com.br/synthetic"
    with (
        patch("src.scraper.DoctoraliaScraper", return_value=scraper),
        patch("src.config.settings.AppConfig.load", return_value=config),
        patch("src.scraper.Remote", side_effect=remote),
        patch("src.scraper.time.sleep"),
    ):
        if execution == "sync":
            result = _scrape_run(SimpleNamespace(doctor_url=url), config).model_dump()
        else:
            result = scrape_and_process({"doctor_url": url})
    assert result["status"] == "failed"
    assert result["collection"]["stop_reason"] == error_name
    assert "secret" not in str(result)
    assert len(drivers) == 6
    for driver in drivers:
        driver.quit.assert_called_once()


@pytest.mark.parametrize("execution", ["sync", "worker"])
def test_partial_collection_is_selectable_and_editable_after_publication(
    tmp_path, execution
):
    import json
    from unittest.mock import MagicMock

    from src.api.v1.routers.scrape import _scrape_run
    from src.jobs.tasks import scrape_and_process
    from src.services.workspace_service import WorkspaceService

    url = "https://www.doctoralia.com.br/synthetic"
    complete = {
        "url": url,
        "doctor_name": "Synthetic",
        "extraction_timestamp": "2026-01-01",
        "collection": {"status": "complete"},
        "reviews": [{"id": "old"}],
    }
    (tmp_path / "complete.json").write_text(json.dumps(complete))
    config = MagicMock(data_dir=tmp_path)
    scraper = MagicMock()
    scraper.scrape_reviews.return_value = {
        "url": url,
        "doctor_name": "Synthetic",
        "extraction_timestamp": "2026-01-02",
        "reviews": [{"id": "new", "comment": "synthetic"}],
        "collection": {
            "status": "partial",
            "expected_count": 2,
            "extracted_count": 1,
            "stop_reason": "load_timeout",
        },
    }

    def save(payload):
        path = tmp_path / "partial.json"
        path.write_text(json.dumps(payload))
        return path

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
    assert result["status"] == "partial"
    service = WorkspaceService(tmp_path)
    profile = service.make_profile_id(url, "Synthetic")
    assert (
        service.get_profile_detail(profile)["latest_reviews"][0]["review_id"] == "old"
    )
    assert (
        service.get_profile_detail(profile, snapshot="partial.json")["latest_reviews"][
            0
        ]["review_id"]
        == "new"
    )
    service.save_generated_response(profile, "new", "saved", snapshot="partial.json")
    assert (
        service.list_pending_responses(profile, snapshot="partial.json")["items"][0][
            "generated_response"
        ]
        == "saved"
    )
    assert json.loads((tmp_path / "complete.json").read_text()) == complete


@pytest.mark.parametrize("execution", ["sync", "worker"])
def test_snapshot_persistence_failure_reports_failure(tmp_path, execution):
    from unittest.mock import MagicMock

    from src.api.v1.routers.scrape import _scrape_run
    from src.jobs.tasks import scrape_and_process

    config = MagicMock(data_dir=tmp_path)
    scraper = MagicMock()
    url = "https://www.doctoralia.com.br/synthetic"
    scraper.scrape_reviews.return_value = {
        "url": url,
        "doctor_name": "Synthetic",
        "reviews": [],
        "collection": {
            "status": "complete",
            "expected_count": 0,
            "extracted_count": 0,
            "stop_reason": "exhausted",
        },
    }
    scraper.save_data.return_value = None
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
    assert result["status"] == "failed"
    assert result["collection"]["stop_reason"] == "RuntimeError"
    assert result["collection"]["duration_ms"] >= 0
    assert not list(tmp_path.glob("*.json"))


@pytest.mark.parametrize(
    "error_name", ["SessionNotCreatedException", "WebDriverException"]
)
@pytest.mark.parametrize("execution", ["sync", "worker"])
def test_remote_constructor_failure_preserves_selenium_type(
    tmp_path, error_name, execution
):
    from contextlib import nullcontext
    from unittest.mock import MagicMock

    from selenium.common import exceptions

    from src.api.v1.routers.scrape import _scrape_run
    from src.jobs.tasks import scrape_and_process
    from src.scraper import DoctoraliaScraper

    config = MagicMock(data_dir=tmp_path)
    config.scraping.max_retries = 2
    config.integrations.selenium_remote_url = "http://synthetic.invalid"
    scraper = DoctoraliaScraper.__new__(DoctoraliaScraper)
    scraper.config = config
    scraper.logger = MagicMock()
    scraper.driver = None
    scraper.performance_monitor = MagicMock()
    scraper.performance_monitor.track_operation.return_value = nullcontext(MagicMock())
    callbacks = []
    with (
        patch("src.scraper.DoctoraliaScraper", return_value=scraper),
        patch("src.config.settings.AppConfig.load", return_value=config),
        patch(
            "src.scraper.Remote", side_effect=getattr(exceptions, error_name)("secret")
        ) as remote,
        patch.object(
            scraper, "safe_driver_quit", wraps=scraper.safe_driver_quit
        ) as cleanup,
        patch("src.scraper.time.sleep"),
        patch(
            "src.jobs.tasks.post_callback",
            side_effect=lambda _, result, job: callbacks.append(result),
        ),
        patch("src.jobs.tasks._update_job_meta") as meta,
    ):
        url = "https://www.doctoralia.com.br/synthetic"
        if execution == "sync":
            result = _scrape_run(SimpleNamespace(doctor_url=url), config).model_dump()
        else:
            result = scrape_and_process(
                {"doctor_url": url}, callback_url="https://invalid"
            )
    assert remote.call_count == 6
    assert cleanup.call_count == 8
    assert result["status"] == "failed"
    assert result["collection"]["stop_reason"] == error_name
    assert "secret" not in str((result, callbacks, meta.call_args_list))
    if callbacks:
        assert callbacks[0] == result
