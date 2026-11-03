from types import SimpleNamespace

import pytest

from src.api.v1.routers.jobs import _map_job_status
from src.services.scrape_completeness import (
    advertised_review_count,
    collection_info,
    result_status,
)
from src.services.workspace_service import WorkspaceService


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        (
            '<section id="profile-reviews"><p class="mb-0">164 opiniões</p></section>',
            164,
        ),
        (
            '<section id="profile-reviews"><p class="mb-0">1.234 opiniões</p></section>',
            1234,
        ),
        ('<section id="profile-reviews"><p class="mb-0">1 opinião</p></section>', 1),
        ('<section id="profile-reviews"><p>164 opiniões</p></section>', None),
        ('<section id="profile-reviews"><p class="mb-0">...</p></section>', None),
    ],
)
def test_advertised_review_count(markup, expected):
    assert advertised_review_count(markup) == expected


@pytest.mark.parametrize(
    ("total", "extracted", "reason", "status"),
    [
        (10, 10, "exhausted", "complete"),
        (10, 9, "exhausted", "partial"),
        (None, 10, "exhausted", "unknown"),
        (10, 10, "load_timeout", "partial"),
        (0, 0, "exhausted", "complete"),
    ],
)
def test_collection_info(total, extracted, reason, status):
    info = collection_info(total, extracted, reason)
    assert info == {
        "status": status,
        "expected_count": total,
        "extracted_count": extracted,
        "stop_reason": reason,
    }


def test_unknown_collection_does_not_report_full_success():
    assert result_status(collection_info(None, 10, "exhausted")) == "partial"
    assert result_status(None) == "completed"  # Legacy results have no metadata.


def test_finished_partial_job_is_not_mapped_to_completed():
    job = SimpleNamespace(
        result={"status": "partial"},
        is_queued=False,
        is_deferred=False,
        is_started=False,
        is_finished=True,
        is_failed=False,
    )
    assert _map_job_status(job) == "partial"


def test_missing_reviews_section_has_no_advertised_count():
    assert advertised_review_count("<main><p>164 opiniões</p></main>") is None


def test_complete_snapshot_replaces_partial_even_when_older():
    from datetime import datetime

    partial = {
        "profile_id": "a",
        "extracted_ts": datetime(2026, 2, 1),
        "collection": {"status": "partial"},
    }
    complete = {
        "profile_id": "a",
        "extracted_ts": datetime(2026, 1, 1),
        "collection": {"status": "complete"},
    }
    assert WorkspaceService._latest_by_profile([partial, complete])["a"] == complete
