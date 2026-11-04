import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.jobs.tasks import (
    _build_snapshot_payload,
    _merge_generated_responses,
    _run_response_generation,
    _run_sentiment_analysis,
    _update_job_meta,
    post_callback,
    scrape_and_process,
)
from src.services.review_reconciliation import (
    carry_forward_drafts as _carry_forward_drafts,
)
from src.services.review_reconciliation import carry_forward_historical_drafts


def test_carry_forward_drafts_matches_legacy_without_using_position():
    old = [
        {
            "id": 1,
            "author": "Ana",
            "comment": "Muito bom",
            "generated_response": "Obrigada",
        },
        {"id": 2, "author": "Bia", "comment": "Excelente"},
    ]
    new = [
        {"id": "doctoralia:2", "author": "Bia", "comment": "Excelente"},
        {"id": "doctoralia:1", "author": "Ana", "comment": "Muito bom"},
    ]
    result = _carry_forward_drafts(new, old)
    assert "generated_response" not in result[0]
    assert result[1]["generated_response"] == "Obrigada"


def test_carry_forward_drafts_rejects_ambiguous_legacy_matches():
    old = [
        {"id": 1, "author": "Ana", "comment": "Bom", "generated_response": "Rascunho"}
    ]
    new = [
        {"id": "doctoralia:1", "author": "Ana", "comment": "Bom"},
        {"id": "doctoralia:2", "author": "Ana", "comment": "Bom"},
    ]
    assert all(
        "generated_response" not in item for item in _carry_forward_drafts(new, old)
    )


def test_carry_forward_drafts_matches_unique_source_id_and_keeps_existing():
    old = [{"id": "doctoralia:1", "comment": "Antigo", "generated_response": "Editado"}]
    new = [{"id": "doctoralia:1", "comment": "Atualizado"}]
    carried = _carry_forward_drafts(new, old)
    assert carried[0]["generated_response"] == "Editado"
    assert (
        _merge_generated_responses(
            carried, {"responses": [{"review_id": "doctoralia:1", "text": "Nova"}]}
        )[0]["generated_response"]
        == "Editado"
    )


def test_carry_forward_drafts_does_not_join_distinct_source_ids():
    old = [
        {
            "id": "doctoralia:1",
            "author": "Ana",
            "comment": "Bom",
            "generated_response": "Rascunho",
        }
    ]
    new = [{"id": "doctoralia:2", "author": "Ana", "comment": "Bom"}]
    assert "generated_response" not in _carry_forward_drafts(new, old)[0]


def test_drafts_are_not_transferred_to_or_from_ambiguous_identity():
    old = {
        "id": "doctoralia:1",
        "author": "Ana",
        "comment": "Bom",
        "generated_response": "Rascunho",
    }
    ambiguous = {"id": "ambiguous:1", "author": "Ana", "comment": "Bom"}
    assert not _carry_forward_drafts([ambiguous], [old])[0].get("generated_response")
    assert not _carry_forward_drafts(
        [old | {"generated_response": ""}],
        [ambiguous | {"generated_response": "Rascunho"}],
    )[0].get("generated_response")


def test_recovers_source_draft_from_older_snapshot_when_absent_in_latest():
    new = [{"id": "doctoralia:1", "author": "Ana", "comment": "Bom"}]
    older = [{**new[0], "generated_response": "Editado"}]
    result = carry_forward_historical_drafts(new, [[], older])
    assert result[0]["generated_response"] == "Editado"


def test_historical_recovery_without_snapshots_leaves_reviews_unchanged():
    review = {"id": "doctoralia:1", "comment": "Bom"}
    result = carry_forward_historical_drafts([review], [])
    assert result == [review]
    assert result[0] is not review


def test_historical_recovery_does_not_restore_cleared_or_ambiguous_drafts():
    review = {"id": "doctoralia:1", "author": "Ana", "comment": "Bom"}
    older = [{**review, "generated_response": "Anterior"}]
    for newer in ([review], [{**review, "id": 1}], [*older, *older]):
        result = carry_forward_historical_drafts([review], [newer, older])
        assert not result[0].get("generated_response")


def test_historical_recovery_uses_most_recent_older_occurrence():
    review = {"id": "doctoralia:1", "author": "Ana", "comment": "Bom"}
    history = [
        [],
        [{**review, "generated_response": "Nova"}],
        [{**review, "generated_response": "Antiga"}],
    ]
    assert (
        carry_forward_historical_drafts([review], history)[0]["generated_response"]
        == "Nova"
    )


def test_job_preserves_legacy_draft_on_next_snapshot(tmp_path):
    url = "https://www.doctoralia.com.br/perfil/exemplo"
    old_review = {
        "id": 1,
        "author": "Ana",
        "comment": "Muito bom",
        "generated_response": "Obrigada",
    }
    (tmp_path / "old.json").write_text(
        json.dumps(
            {
                "doctor_name": "Dra. Ana",
                "url": url,
                "extraction_timestamp": "2026-01-01T10:00:00",
                "reviews": [old_review],
            }
        )
    )
    config = MagicMock(data_dir=tmp_path)
    with (
        patch("src.config.settings.AppConfig.load", return_value=config),
        patch("src.scraper.DoctoraliaScraper") as cls,
    ):
        scraper = cls.return_value
        scraper.scrape_reviews.return_value = {
            "doctor_name": "Dra. Ana",
            "url": url,
            "reviews": [
                {"id": "doctoralia:123", "author": "Ana", "comment": "Muito bom"}
            ],
        }
        scraper.save_data.return_value = tmp_path / "new.json"
        result = scrape_and_process({"doctor_url": url})
    assert result["status"] == "completed"
    assert (
        scraper.save_data.call_args.args[0]["reviews"][0]["generated_response"]
        == "Obrigada"
    )


def test_job_recovers_draft_when_review_was_absent_from_previous_snapshot(tmp_path):
    url = "https://www.doctoralia.com.br/perfil/exemplo"
    review = {"id": "doctoralia:123", "author": "Ana", "comment": "Muito bom"}
    for filename, timestamp, reviews in [
        (
            "old.json",
            "2026-01-01T10:00:00",
            [{**review, "generated_response": "Editado"}],
        ),
        ("latest.json", "2026-01-02T10:00:00", []),
    ]:
        (tmp_path / filename).write_text(
            json.dumps(
                {
                    "doctor_name": "Dra. Ana",
                    "url": url,
                    "extraction_timestamp": timestamp,
                    "reviews": reviews,
                }
            )
        )
    with (
        patch(
            "src.config.settings.AppConfig.load",
            return_value=MagicMock(data_dir=tmp_path),
        ),
        patch("src.scraper.DoctoraliaScraper") as cls,
    ):
        scraper = cls.return_value
        scraper.scrape_reviews.return_value = {
            "doctor_name": "Dra. Ana",
            "url": url,
            "reviews": [review],
        }
        scraper.save_data.return_value = tmp_path / "new.json"
        scrape_and_process({"doctor_url": url})
    assert (
        scraper.save_data.call_args.args[0]["reviews"][0]["generated_response"]
        == "Editado"
    )


def test_job_does_not_recover_draft_when_snapshot_times_are_ambiguous(tmp_path):
    url = "https://www.doctoralia.com.br/perfil/exemplo"
    review = {"id": "doctoralia:123", "author": "Ana", "comment": "Muito bom"}
    for filename, reviews in [
        ("a.json", []),
        ("b.json", [{**review, "generated_response": "Editado"}]),
    ]:
        (tmp_path / filename).write_text(
            json.dumps(
                {
                    "doctor_name": "Dra. Ana",
                    "url": url,
                    "extraction_timestamp": "2026-01-01T10:00:00",
                    "reviews": reviews,
                }
            )
        )
    os.utime(tmp_path / "a.json", (100, 100))
    os.utime(tmp_path / "b.json", (101, 101))
    with (
        patch(
            "src.config.settings.AppConfig.load",
            return_value=MagicMock(data_dir=tmp_path),
        ),
        patch("src.scraper.DoctoraliaScraper") as cls,
    ):
        scraper = cls.return_value
        scraper.scrape_reviews.return_value = {
            "doctor_name": "Dra. Ana",
            "url": url,
            "reviews": [review],
        }
        scraper.save_data.return_value = tmp_path / "new.json"
        scrape_and_process({"doctor_url": url})
    assert not scraper.save_data.call_args.args[0]["reviews"][0].get(
        "generated_response"
    )


def test_job_reports_partial_collection(tmp_path):
    info = {
        "status": "partial",
        "expected_count": 100,
        "extracted_count": 2,
        "stop_reason": "load_timeout",
    }
    url = "https://www.doctoralia.com.br/perfil/exemplo"
    with (
        patch(
            "src.config.settings.AppConfig.load",
            return_value=MagicMock(data_dir=tmp_path),
        ),
        patch("src.scraper.DoctoraliaScraper") as cls,
    ):
        scraper = cls.return_value
        scraper.scrape_reviews.return_value = {
            "doctor_name": "Dra Ana",
            "url": url,
            "reviews": [],
            "collection": info,
        }
        scraper.save_data.return_value = tmp_path / "new.json"
        result = scrape_and_process({"doctor_url": url})
    assert result["status"] == "partial"
    assert result["collection"] == info
    assert scraper.save_data.call_args.args[0]["collection"] == info


def test_job_uses_draft_edited_during_generation(tmp_path):
    url = "https://www.doctoralia.com.br/perfil/exemplo"
    snapshot = tmp_path / "old.json"
    old = {
        "doctor_name": "Dra Ana",
        "url": url,
        "extraction_timestamp": "2026-01-01T10:00:00",
        "reviews": [
            {
                "id": "doctoralia:123",
                "author": "Ana",
                "comment": "Ótimo",
                "generated_response": "Antes",
            }
        ],
    }
    snapshot.write_text(json.dumps(old))
    config = MagicMock(data_dir=tmp_path)

    def generate(*args, **kwargs):
        old["reviews"][0]["generated_response"] = "Editada durante geração"
        snapshot.write_text(json.dumps(old))
        return {"responses": [{"review_id": "doctoralia:123", "text": "Nova sugestão"}]}

    with (
        patch("src.config.settings.AppConfig.load", return_value=config),
        patch("src.scraper.DoctoraliaScraper") as cls,
        patch("src.jobs.tasks._run_response_generation", side_effect=generate),
    ):
        scraper = cls.return_value
        scraper.scrape_reviews.return_value = {
            "doctor_name": "Dra Ana",
            "url": url,
            "reviews": [{"id": "doctoralia:123", "author": "Ana", "comment": "Ótimo"}],
        }
        scraper.save_data.return_value = tmp_path / "new.json"
        result = scrape_and_process({"doctor_url": url, "include_generation": True})
    assert result["status"] == "completed"
    assert (
        scraper.save_data.call_args.args[0]["reviews"][0]["generated_response"]
        == "Editada durante geração"
    )


def test_scrape_and_process_persists_snapshot_with_generated_responses(tmp_path):
    config = MagicMock()
    config.data_dir = tmp_path

    saved_path = tmp_path / "snapshot.json"

    scraper_result = {
        "doctor_name": "Dra. Ana",
        "url": "https://example.com/dra-ana",
        "extraction_timestamp": "2026-03-14T20:00:00",
        "reviews": [
            {
                "id": 1,
                "author": "Maria",
                "comment": "Excelente atendimento",
                "rating": 5,
                "date": "2026-03-13",
            }
        ],
        "total_reviews": 1,
    }

    generation_data = {
        "responses": [
            {
                "review_id": "1",
                "text": "Obrigada pelo carinho e pela confiança.",
                "provider": "local",
                "model": "template",
                "status": "generated",
            }
        ],
        "model": {"provider": "local"},
    }

    with patch("src.config.settings.AppConfig.load", return_value=config):
        with patch("src.scraper.DoctoraliaScraper") as mock_scraper_cls:
            with patch(
                "src.jobs.tasks._run_response_generation", return_value=generation_data
            ):
                mock_scraper = MagicMock()
                mock_scraper.scrape_reviews.return_value = scraper_result
                mock_scraper.save_data.return_value = saved_path
                mock_scraper_cls.return_value = mock_scraper

                result = scrape_and_process(
                    {
                        "doctor_url": "https://example.com/dra-ana",
                        "include_generation": True,
                        "include_analysis": False,
                        "generation_mode": "local",
                        "language": "pt-BR",
                    },
                    job_id="job-123",
                )

    assert result["status"] == "completed"
    assert result["reviews"][0]["id"] == "1"
    mock_scraper.save_data.assert_called_once()

    snapshot_payload = mock_scraper.save_data.call_args.args[0]
    assert snapshot_payload["doctor_name"] == "Dra. Ana"
    assert snapshot_payload["total_reviews"] == 1
    assert snapshot_payload["reviews"][0]["id"] == "1"
    assert (
        snapshot_payload["reviews"][0]["generated_response"]
        == "Obrigada pelo carinho e pela confiança."
    )
    assert snapshot_payload["url"] == "https://example.com/dra-ana"


def test_update_job_meta_persists_progress_and_message():
    fake_job = MagicMock()
    fake_job.meta = {}

    with patch("rq.get_current_job", return_value=fake_job):
        _update_job_meta(progress=55, message="Scraping em andamento")

    assert fake_job.meta["progress"] == 55
    assert fake_job.meta["message"] == "Scraping em andamento"
    fake_job.save_meta.assert_called_once()


def test_merge_generated_responses_adds_generated_text_to_matching_reviews():
    reviews = [{"id": "1", "comment": "Excelente"}, {"id": "2", "comment": "Bom"}]
    generation_data = {
        "responses": [
            {"review_id": "2", "text": "Obrigada pelo retorno!"},
            {"review_id": "3", "text": "Nao deve ser anexado"},
        ]
    }

    merged = _merge_generated_responses(reviews, generation_data)

    assert merged[0].get("generated_response") is None
    assert merged[1]["generated_response"] == "Obrigada pelo retorno!"


def test_build_snapshot_payload_prefers_doctor_metadata_and_counts_reviews():
    scraper_result = {"doctor_name": "Fallback", "url": "https://fallback.example.com"}
    doctor_data = {
        "name": "Dra. Ana",
        "url": "https://example.com/dra-ana",
        "specialty": "Ginecologia",
        "location": "Sao Paulo",
        "rating": 4.9,
    }
    reviews_data = [{"id": "1", "comment": "Excelente"}]

    payload = _build_snapshot_payload(scraper_result, doctor_data, reviews_data)

    assert payload["doctor_name"] == "Dra. Ana"
    assert payload["url"] == "https://example.com/dra-ana"
    assert payload["specialty"] == "Ginecologia"
    assert payload["location"] == "Sao Paulo"
    assert payload["average_rating"] == 4.9
    assert payload["total_reviews"] == 1
    assert payload["reviews"][0]["id"] == "1"
    assert "extraction_timestamp" in payload


def test_post_callback_returns_true_when_request_succeeds():
    response = MagicMock()
    session = MagicMock()
    session.post.return_value = response

    with patch("src.jobs.tasks.requests.Session", return_value=session):
        with patch(
            "src.jobs.tasks.create_webhook_signature",
            return_value=("1710000000.0", "sha256=test-signature"),
        ):
            ok = post_callback(
                "https://hooks.example.com/callback",
                {"status": "completed"},
                job_id="job-123",
            )

    assert ok is True
    session.post.assert_called_once()
    _, kwargs = session.post.call_args
    assert kwargs["headers"]["X-Signature"] == "sha256=test-signature"
    assert kwargs["headers"]["X-Job-Id"] == "job-123"
    response.raise_for_status.assert_called_once()


def test_post_callback_returns_false_when_request_fails():
    session = MagicMock()
    session.post.side_effect = RuntimeError("network down")

    with patch("src.jobs.tasks.requests.Session", return_value=session):
        ok = post_callback("https://hooks.example.com/callback", {"status": "failed"})

    assert ok is False


def test_run_sentiment_analysis_aggregates_scores():
    analyzer = MagicMock()
    analyzer.sia.polarity_scores.side_effect = [
        {"compound": 0.5, "pos": 0.7, "neu": 0.2, "neg": 0.1},
        {"compound": -0.1, "pos": 0.2, "neu": 0.3, "neg": 0.5},
    ]

    with patch(
        "src.response_quality_analyzer.ResponseQualityAnalyzer", return_value=analyzer
    ):
        result = _run_sentiment_analysis(
            [{"comment": "Muito bom"}, {"comment": "Pode melhorar"}]
        )

    assert result["summary"] == "Analyzed 2 reviews"
    assert result["sentiment"]["compound"] == 0.2
    assert result["quality_score"] == 20.0


def test_run_response_generation_marks_errors_and_local_fallback():
    config = SimpleNamespace(generation=SimpleNamespace(mode="openai"))
    generator = MagicMock()
    generator.generate_response_with_metadata.side_effect = [
        {
            "text": "Obrigada pela avaliacao!",
            "model": {"provider": "openai", "name": "gpt-4.1-mini", "mode": "local"},
        },
        RuntimeError("provider timeout"),
    ]

    reviews = [{"id": "1", "comment": "Excelente"}, {"id": "2", "comment": "Bom"}]
    request_data = {"generation_mode": "openai", "language": "pt-BR"}
    doctor_data = {"name": "Dra. Ana", "specialty": "Ginecologia"}

    with patch("src.config.settings.AppConfig.load", return_value=config):
        with patch("src.response_generator.ResponseGenerator", return_value=generator):
            result = _run_response_generation(reviews, request_data, doctor_data)

    assert result["model"]["provider"] == "openai"
    assert result["responses"][0]["status"] == "generated"
    assert result["responses"][0]["fallback_used"] is True
    assert result["responses"][1]["status"] == "empty"
    assert result["responses"][1]["error"] == "provider timeout"
