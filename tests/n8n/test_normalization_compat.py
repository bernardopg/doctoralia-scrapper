"""Contract checks for both normalization import paths."""

from datetime import datetime

import pytest

from src import normalization as shared
from src.integrations.n8n import normalize as legacy


@pytest.mark.parametrize(
    "name",
    [
        "_build_review_id",
        "sanitize_raw_reviews",
        "normalize_doctor",
        "normalize_reviews",
        "normalize_analysis",
        "normalize_generation",
        "make_unified_result",
        "extract_scraper_result",
    ],
)
def test_legacy_exports_are_the_shared_functions(name):
    assert getattr(legacy, name) is getattr(shared, name)


@pytest.mark.parametrize(
    "status,collection_status",
    [
        ("completed", "complete"),
        ("partial", "partial"),
        ("partial", "unknown"),
        ("failed", "partial"),
    ],
)
def test_unified_contract_with_fixed_input_and_times(status, collection_status):
    start = datetime(2026, 1, 2, 3, 4, 5)
    end = datetime(2026, 1, 2, 3, 4, 6)
    doctor = {"id": 7, "name": "Ana", "url": "https://example.org", "tag": "x"}
    reviews = [{"id": 42, "date": "2026-01-01", "comment": "Bom", "author": "A"}]
    kwargs = dict(
        doctor_data=doctor,
        reviews_data=reviews,
        analysis_data={"sentiment": {"positive": 0.8}},
        generation_data={"responses": [{"review_id": 42, "text": "Obrigado"}]},
        job_id="job-1",
        status=status,
        start_time=start,
        end_time=end,
        collection={"status": collection_status},
    )
    old = legacy.make_unified_result(**kwargs)
    result = shared.make_unified_result(**kwargs)
    assert old == result
    assert result.doctor.id == "7"
    assert result.doctor.extra == {"tag": "x"}
    assert result.reviews[0].id == "42"
    assert result.reviews[0].author.name == "A"
    assert result.analysis.sentiments.positive == 0.8
    assert result.generation.responses[0].review_id == "42"
    assert result.metrics.duration_ms == 1000
    assert result.metrics.start_ts == start and result.metrics.end_ts == end
    assert result.collection == {"status": collection_status}
    assert result.status == status and result.job_id == "job-1"


def test_missing_optional_data_and_stable_generated_identity():
    scraped = {"reviews": [{"date": "2026-01-01", "text": "Bom"}]}
    doctor, reviews = shared.extract_scraper_result(scraped)
    assert (doctor, reviews) == legacy.extract_scraper_result(scraped)
    result = shared.make_unified_result(
        doctor, reviews, start_time=datetime(2026, 1, 1), end_time=datetime(2026, 1, 1)
    )
    assert result.doctor.name == "Unknown"
    assert result.reviews[0].id == reviews[0]["id"]
    assert result.analysis is None and result.generation is None
    assert result.collection is None
