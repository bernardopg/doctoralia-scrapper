"""Exercise publication through the real atomic snapshot writer."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from src.api.schemas.requests import ScrapeRequest
from src.api.v1.routers.scrape import _scrape_run
from src.integrations.n8n.normalize import normalize_reviews
from src.jobs.tasks import scrape_and_process
from src.scraper import DoctoraliaScraper
from src.services.workspace_service import WorkspaceService

URL = "https://www.doctoralia.com.br/test"
REVIEW = {
    "id": "doctoralia:42",
    "author": "Ana",
    "comment": "Boa",
    "date": "2026-01-01",
}


def snapshot(path, date, draft=None, status="partial"):
    review = dict(REVIEW)
    if draft is not None:
        review["generated_response"] = draft
    path.write_text(
        json.dumps(
            {
                "doctor_name": "Test",
                "url": URL,
                "extraction_timestamp": date,
                "collection": {"status": status},
                "reviews": [review],
            }
        )
    )


def scraper_for(tmp_path):
    config = MagicMock(data_dir=tmp_path)
    scraper = DoctoraliaScraper.__new__(DoctoraliaScraper)
    scraper.config = config
    scraper.logger = logging.getLogger(__name__)
    scraper.scrape_reviews = MagicMock(  # type: ignore[method-assign]
        return_value={
            "doctor_name": "Test",
            "url": URL,
            "extraction_timestamp": "2026-01-03T00:00:00Z",
            "collection": {"status": "complete"},
            "reviews": [dict(REVIEW)],
        }
    )
    return scraper, config


@pytest.mark.parametrize("execution", ["sync", "worker", "direct"])
@pytest.mark.parametrize("newer,expected", [(None, None), ("new", "new")])
def test_real_publication_uses_newest_legacy_snapshot(
    tmp_path, execution, newer, expected
):
    snapshot(tmp_path / "one.json", "2026-01-01T00:00:00Z", "old", "complete")
    snapshot(tmp_path / "two.json", "2026-01-02T00:00:00Z", newer)
    scraper, config = scraper_for(tmp_path)
    callbacks = []
    with (
        patch("src.scraper.DoctoraliaScraper", return_value=scraper),
        patch("src.config.settings.AppConfig.load", return_value=config),
        patch(
            "src.jobs.tasks.post_callback",
            side_effect=lambda _, result, job: callbacks.append(result),
        ),
    ):
        if execution == "sync":
            result = _scrape_run(
                ScrapeRequest.model_validate(
                    {
                        "doctor_url": URL,
                        "include_analysis": False,
                        "include_generation": False,
                    }
                ),
                config,
            ).model_dump()
        elif execution == "worker":
            result = scrape_and_process(
                {"doctor_url": URL}, callback_url="https://invalid"
            )
        else:
            scraper.save_data(scraper.scrape_reviews(URL))
            result = None
    written = [
        p for p in tmp_path.glob("*.json") if p.name not in {"one.json", "two.json"}
    ]
    assert len(written) == 1
    review = json.loads(written[0].read_text())["reviews"][0]
    assert review.get("generated_response") == expected
    if result:
        assert result["reviews"] == [normalize_reviews([review])[0].model_dump()]
        if callbacks:
            assert callbacks[0] == result


def test_historical_edit_and_clear_survive_later_collection(tmp_path):
    snapshot(tmp_path / "one.json", "2026-01-01T00:00:00Z", "old", "complete")
    snapshot(tmp_path / "two.json", "2026-01-02T00:00:00Z", "new")
    scraper, _ = scraper_for(tmp_path)
    service = WorkspaceService(tmp_path)
    profile = service.make_profile_id(URL, "Test")
    for draft in ("historical edit", ""):
        assert service.save_generated_response(profile, REVIEW["id"], draft, "one.json")
        data = scraper.scrape_reviews(URL)
        target = scraper.save_data(data)
        assert (
            json.loads(target.read_text())["reviews"][0]["generated_response"] == draft
        )


def test_edit_during_generation_wins_at_real_publication(tmp_path):
    snapshot(tmp_path / "one.json", "2026-01-01T00:00:00Z", "old")
    scraper, config = scraper_for(tmp_path)
    service = WorkspaceService(tmp_path)
    profile = service.make_profile_id(URL, "Test")

    def generate(*args):
        assert service.save_generated_response(
            profile, REVIEW["id"], "edit", "one.json"
        )
        return {"responses": [{"review_id": REVIEW["id"], "text": "generated"}]}

    with (
        patch("src.scraper.DoctoraliaScraper", return_value=scraper),
        patch("src.config.settings.AppConfig.load", return_value=config),
        patch("src.jobs.tasks._run_response_generation", side_effect=generate),
    ):
        result = scrape_and_process({"doctor_url": URL, "include_generation": True})
    written = next(p for p in tmp_path.glob("*.json") if p.name != "one.json")
    review = json.loads(written.read_text())["reviews"][0]
    assert review["generated_response"] == "edit"
    assert result["reviews"][0]["metadata"]["generated_response"] == "edit"


@pytest.mark.parametrize("case", ["tie", "missing", "duplicate"])
def test_unsafe_legacy_order_or_identity_never_carries_draft(tmp_path, case):
    snapshot(tmp_path / "one.json", "2026-01-01T00:00:00Z", "old")
    snapshot(tmp_path / "two.json", "2026-01-01T00:00:00Z", None)
    if case != "tie":
        payload = json.loads((tmp_path / "two.json").read_text())
        payload["extraction_timestamp"] = (
            None if case == "missing" else "2026-01-02T00:00:00Z"
        )
        if case == "duplicate":
            payload["reviews"].append(dict(REVIEW, generated_response="other"))
        (tmp_path / "two.json").write_text(json.dumps(payload))
    scraper, _ = scraper_for(tmp_path)
    saved = scraper.save_data(scraper.scrape_reviews(URL))
    assert not json.loads(saved.read_text())["reviews"][0].get("generated_response")


@pytest.mark.parametrize("execution", ["sync", "worker"])
def test_real_write_failure_reports_failure(tmp_path, execution):
    scraper, config = scraper_for(tmp_path)
    callbacks = []
    with (
        patch("src.scraper.DoctoraliaScraper", return_value=scraper),
        patch("src.config.settings.AppConfig.load", return_value=config),
        patch("src.scraper.write_json_atomic", side_effect=OSError("secret")),
        patch(
            "src.jobs.tasks.post_callback",
            side_effect=lambda _, result, job: callbacks.append(result),
        ),
    ):
        if execution == "sync":
            result = _scrape_run(
                ScrapeRequest.model_validate(
                    {
                        "doctor_url": URL,
                        "include_analysis": False,
                        "include_generation": False,
                    }
                ),
                config,
            ).model_dump()
        else:
            result = scrape_and_process(
                {"doctor_url": URL}, callback_url="https://invalid"
            )
    assert result["status"] == "failed"
    assert "secret" not in str(result)
    assert not list(tmp_path.glob("*.json"))
    if callbacks:
        assert callbacks[0] == result


def test_requested_generation_after_clearing_is_published_and_remains_authoritative(
    tmp_path,
):
    snapshot(tmp_path / "one.json", "2026-01-01T00:00:00Z", "old")
    scraper, config = scraper_for(tmp_path)
    service = WorkspaceService(tmp_path)
    profile = service.make_profile_id(URL, "Test")
    assert service.save_generated_response(profile, REVIEW["id"], "", "one.json")
    with (
        patch("src.scraper.DoctoraliaScraper", return_value=scraper),
        patch("src.config.settings.AppConfig.load", return_value=config),
        patch(
            "src.jobs.tasks._run_response_generation",
            return_value={
                "responses": [{"review_id": REVIEW["id"], "text": "new generated"}]
            },
        ),
    ):
        result = scrape_and_process({"doctor_url": URL, "include_generation": True})
    assert result["reviews"][0]["metadata"]["generated_response"] == "new generated"
    saved = scraper.save_data(scraper.scrape_reviews(URL))
    assert (
        json.loads(saved.read_text())["reviews"][0]["generated_response"]
        == "new generated"
    )


def test_conflicting_edit_versions_do_not_choose_between_snapshots(tmp_path):
    for filename, draft in (("one.json", "first"), ("two.json", "second")):
        snapshot(tmp_path / filename, "2026-01-01T00:00:00Z", draft)
        data = json.loads((tmp_path / filename).read_text())
        data["reviews"][0]["draft_edit"] = {"version": 1, "cleared": False}
        (tmp_path / filename).write_text(json.dumps(data))
    scraper, _ = scraper_for(tmp_path)
    saved = scraper.save_data(scraper.scrape_reviews(URL))
    assert not json.loads(saved.read_text())["reviews"][0].get("generated_response")


def test_generated_suggestions_do_not_attach_to_duplicate_ids(tmp_path):
    scraper, config = scraper_for(tmp_path)
    scraper.scrape_reviews.return_value["reviews"] = [dict(REVIEW), dict(REVIEW)]
    with (
        patch("src.scraper.DoctoraliaScraper", return_value=scraper),
        patch("src.config.settings.AppConfig.load", return_value=config),
        patch(
            "src.jobs.tasks._run_response_generation",
            return_value={"responses": [{"review_id": REVIEW["id"], "text": "unsafe"}]},
        ),
    ):
        result = scrape_and_process({"doctor_url": URL, "include_generation": True})
    saved = next(tmp_path.glob("*.json"))
    reviews = json.loads(saved.read_text())["reviews"]
    assert all(not review.get("generated_response") for review in reviews)
    assert result["reviews"] == [
        item.model_dump() for item in normalize_reviews(reviews)
    ]


@pytest.mark.parametrize("draft", ["edited", ""])
def test_legacy_edit_does_not_transfer_to_duplicate_new_source_ids(tmp_path, draft):
    snapshot(tmp_path / "one.json", "2026-01-01T00:00:00Z", "old")
    original = json.loads((tmp_path / "one.json").read_text())
    original["reviews"][0]["id"] = "legacy:1"
    (tmp_path / "one.json").write_text(json.dumps(original))
    service = WorkspaceService(tmp_path)
    profile = service.make_profile_id(URL, "Test")
    assert service.save_generated_response(profile, "legacy:1", draft, "one.json")
    scraper, _ = scraper_for(tmp_path)
    data = scraper.scrape_reviews(URL)
    data["reviews"] = [dict(REVIEW), dict(REVIEW, author="Bia", comment="Outra")]
    saved = scraper.save_data(data)
    for review in json.loads(saved.read_text())["reviews"]:
        assert "draft_edit" not in review
        assert not review.get("generated_response")
