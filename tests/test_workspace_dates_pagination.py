"""Review-date filters, collection-date filters and pagination (REL-06)."""

import json
import os
from pathlib import Path

import pytest

from src.services import workspace_service as workspace_module
from src.services.workspace_service import WorkspaceService

URL = "https://www.doctoralia.com.br/perfil/exemplo"


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _snapshot(collected_at: str, reviews: list) -> dict:
    return {
        "doctor_name": "Dra Ana",
        "url": URL,
        "extraction_timestamp": collected_at,
        "collection": {"status": "complete"},
        "reviews": reviews,
    }


def _review(review_id: int, date):
    return {"id": f"doctoralia:{review_id}", "comment": f"c{review_id}", "date": date}


@pytest.fixture
def service(tmp_path):
    reviews = [
        _review(1, "2026-01-05T10:00:00"),
        # Published late on 10 January in Brazil; still 10 January even
        # though it is already 11 January in UTC.
        _review(2, "2026-01-10T23:30:00-03:00"),
        _review(3, "2026-02-01"),
        _review(4, None),
        _review(5, "não informado"),
    ]
    _write(tmp_path / "s.json", _snapshot("2026-03-01T09:00:00", reviews))
    return WorkspaceService(tmp_path)


def _ids(payload):
    return [item["review_id"] for item in payload["items"]]


def test_review_date_filter_uses_publication_date_not_collection_date(service):
    payload = service.list_pending_responses(
        review_date_from="2026-01-01", review_date_to="2026-01-10"
    )
    assert sorted(_ids(payload)) == ["doctoralia:1", "doctoralia:2"]
    # The collection happened in March, outside the review range.
    assert all(
        item["collected_at"].startswith("2026-03-01") for item in payload["items"]
    )
    assert payload["summary"]["undated_excluded"] == 2
    assert payload["date_filters"]["review_date_to"] == "2026-01-10"


def test_review_date_keeps_source_offset(service):
    payload = service.list_pending_responses(
        review_date_from="2026-01-11", review_date_to="2026-01-11"
    )
    assert _ids(payload) == []


def test_undated_reviews_are_kept_without_review_filter(service):
    payload = service.list_pending_responses()
    assert len(payload["items"]) == 5
    assert payload["summary"]["undated_excluded"] == 0
    undated = [item for item in payload["items"] if item["review_date"] is None]
    assert len(undated) == 2
    # Undated reviews must never inherit the collection date.
    assert all(item["date"] in (None, "não informado") for item in undated)


def test_collection_date_filter_still_selects_snapshots(service):
    assert service.list_pending_responses(date_from="2026-03-02")["items"] == []
    assert len(service.list_pending_responses(date_to="2026-03-01")["items"]) == 5


def test_profile_detail_filters_reviews_by_publication_date(service):
    profile_id = service.list_profiles()[0]["profile_id"]
    detail = service.get_profile_detail(profile_id, review_date_from="2026-02-01")
    assert [item["review_id"] for item in detail["latest_reviews"]] == ["doctoralia:3"]
    assert detail["latest_reviews"][0]["review_date"] == "2026-02-01"


def test_pagination_returns_requested_slice_and_totals(service):
    first = service.list_pending_responses(page=1, page_size=2)
    second = service.list_pending_responses(page=2, page_size=2)
    last = service.list_pending_responses(page=99, page_size=2)
    assert first["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total_items": 5,
        "total_pages": 3,
    }
    assert len(first["items"]) == 2 and len(second["items"]) == 2
    assert not set(_ids(first)) & set(_ids(second))
    assert last["pagination"]["page"] == 3 and len(last["items"]) == 1
    # Summary counts the whole filtered backlog, not the page.
    assert first["summary"]["pending_reviews"] == 5


@pytest.mark.parametrize(("size", "expected"), [(0, 1), (-5, 1), (1000, 100)])
def test_page_size_is_clamped(service, size, expected):
    payload = service.list_pending_responses(page=1, page_size=size)
    assert payload["pagination"]["page_size"] == expected


def test_without_pagination_all_items_are_returned(service):
    payload = service.list_pending_responses()
    assert payload["pagination"]["total_pages"] == 1
    assert len(payload["items"]) == payload["pagination"]["total_items"] == 5


def test_snapshot_cache_detects_changes_and_isolates_callers(tmp_path, monkeypatch):
    path = tmp_path / "s.json"
    _write(path, _snapshot("2026-03-01T09:00:00", [_review(1, "2026-01-01")]))
    service = WorkspaceService(tmp_path)
    reads = []
    original = WorkspaceService._read_snapshot

    def counting(self, json_file):
        reads.append(json_file.name)
        return original(self, json_file)

    monkeypatch.setattr(WorkspaceService, "_read_snapshot", counting)

    first = service._load_snapshots()
    first[0]["reviews"][0]["comment"] = "mutated by caller"
    second = service._load_snapshots()
    assert reads == ["s.json"]
    assert second[0]["reviews"][0]["comment"] == "c1"

    _write(
        path,
        _snapshot("2026-03-01T09:00:00", [_review(1, "2026-01-01"), _review(2, None)]),
    )
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert len(service._load_snapshots()[0]["reviews"]) == 2
    assert reads == ["s.json", "s.json"]

    path.unlink()
    assert service._load_snapshots() == []
    assert not any(
        key.startswith(str(tmp_path.resolve()))
        for key in workspace_module._snapshot_cache
    )


def test_dashboard_route_passes_review_dates_and_ignores_bad_page(tmp_path):
    from unittest.mock import MagicMock

    from flask import Flask

    from src.dashboard.workspace import create_blueprint

    svc = MagicMock()
    svc.get_user_profile_settings.return_value = {}
    svc.workspace_service.list_pending_responses.return_value = {"items": []}
    app = Flask(__name__)
    app.register_blueprint(create_blueprint(svc))

    response = app.test_client().get(
        "/api/workspace/responses?review_date_from=2026-01-01"
        "&review_date_to=2026-01-31&page=abc&page_size=10"
    )

    assert response.status_code == 200
    kwargs = svc.workspace_service.list_pending_responses.call_args.kwargs
    assert kwargs["review_date_from"] == "2026-01-01"
    assert kwargs["review_date_to"] == "2026-01-31"
    assert kwargs["page"] is None
    assert kwargs["page_size"] == 10
