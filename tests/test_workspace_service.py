import json
from pathlib import Path

from src.services.workspace_service import WorkspaceService


def _write_snapshot(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_workspace_overview_aggregates_profiles_and_pending(tmp_path):
    _write_snapshot(
        tmp_path / "profile_a_1.json",
        {
            "doctor_name": "Dra. Ana",
            "url": "https://www.doctoralia.com.br/medico/ana",
            "specialty": "Ginecologia",
            "extraction_timestamp": "2026-03-10T10:00:00",
            "reviews": [
                {
                    "id": "a-1",
                    "author": "Maria",
                    "comment": "Excelente atendimento",
                    "rating": 5,
                    "date": "2026-03-09",
                },
                {
                    "id": "a-2",
                    "author": "Paula",
                    "comment": "Muito boa",
                    "rating": 4,
                    "date": "2026-03-08",
                    "doctor_reply": "Obrigada.",
                },
            ],
        },
    )
    _write_snapshot(
        tmp_path / "profile_b_1.json",
        {
            "doctor_name": "Dr. Bruno",
            "url": "https://www.doctoralia.com.br/medico/bruno",
            "specialty": "Cardiologia",
            "extraction_timestamp": "2026-03-11T11:30:00",
            "reviews": [
                {
                    "id": "b-1",
                    "author": "Joao",
                    "comment": "Consulta muito clara",
                    "rating": 5,
                    "date": "2026-03-10",
                    "generated_response": "Obrigado pelo feedback.",
                }
            ],
        },
    )

    service = WorkspaceService(tmp_path)
    overview = service.get_overview(
        favorite_profiles=[
            {"profile_url": "https://www.doctoralia.com.br/medico/ana"}
        ]
    )

    assert overview["summary"]["profiles_tracked"] == 2
    assert overview["summary"]["total_scrapes"] == 2
    assert overview["summary"]["unanswered_reviews_current"] == 2
    assert overview["summary"]["generated_suggestions_current"] == 1
    assert overview["summary"]["favorite_profiles_count"] == 1
    assert overview["favorite_profiles"][0]["doctor_name"] == "Dra. Ana"
    assert len(overview["filters"]) == 2


def test_workspace_pending_responses_and_save_generated_response(tmp_path):
    snapshot_path = tmp_path / "profile_a_latest.json"
    _write_snapshot(
        snapshot_path,
        {
            "doctor_name": "Dra. Ana",
            "url": "https://www.doctoralia.com.br/medico/ana",
            "specialty": "Ginecologia",
            "extraction_timestamp": "2026-03-14T09:15:00",
            "reviews": [
                {
                    "id": "a-1",
                    "author": "Maria",
                    "comment": "Excelente atendimento",
                    "rating": 5,
                    "date": "2026-03-13",
                },
                {
                    "id": "a-2",
                    "author": "Paula",
                    "comment": "Muito boa",
                    "rating": 4,
                    "date": "2026-03-12",
                    "doctor_reply": "Obrigada.",
                },
            ],
        },
    )

    service = WorkspaceService(tmp_path)
    profile_id = service.make_profile_id(
        "https://www.doctoralia.com.br/medico/ana", "Dra. Ana"
    )

    pending = service.list_pending_responses(
        favorite_profiles=[
            {"profile_url": "https://www.doctoralia.com.br/medico/ana"}
        ],
        favorites_only=True,
    )

    assert pending["summary"]["pending_reviews"] == 1
    assert pending["summary"]["favorite_pending"] == 1
    assert pending["items"][0]["review_id"] == "a-1"

    saved = service.save_generated_response(
        profile_id=profile_id,
        review_id="a-1",
        generated_response="Obrigada pelo carinho e pela confianca.",
    )

    assert saved is not None
    updated_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    updated_review = next(
        review for review in updated_payload["reviews"] if review["id"] == "a-1"
    )
    assert (
        updated_review["generated_response"]
        == "Obrigada pelo carinho e pela confianca."
    )


def test_workspace_history_prunes_outdated_snapshots(tmp_path):
    _write_snapshot(
        tmp_path / "profile_a_old.json",
        {
            "doctor_name": "Dra. Ana",
            "url": "https://www.doctoralia.com.br/medico/ana",
            "extraction_timestamp": "2026-03-10T09:00:00",
            "reviews": [{"id": "a-1", "comment": "Muito bom"}],
        },
    )
    latest_path = tmp_path / "profile_a_latest.json"
    _write_snapshot(
        latest_path,
        {
            "doctor_name": "Dra. Ana",
            "url": "https://www.doctoralia.com.br/medico/ana",
            "extraction_timestamp": "2026-03-14T09:00:00",
            "reviews": [{"id": "a-2", "comment": "Excelente"}],
        },
    )

    service = WorkspaceService(tmp_path)
    history = service.get_history()

    assert history["summary"]["total_snapshots"] == 2
    assert history["summary"]["outdated_snapshots"] == 1

    result = service.prune_outdated_snapshots()

    assert result["deleted_count"] == 1
    assert latest_path.exists()
    assert not (tmp_path / "profile_a_old.json").exists()


def test_workspace_reports_combines_summary_inventory_and_cleanup(tmp_path):
    _write_snapshot(
        tmp_path / "profile_a_old.json",
        {
            "doctor_name": "Dra. Ana",
            "url": "https://www.doctoralia.com.br/medico/ana",
            "extraction_timestamp": "2026-03-10T09:00:00",
            "reviews": [{"id": "a-1", "comment": "Muito bom", "rating": 5}],
        },
    )
    _write_snapshot(
        tmp_path / "profile_a_latest.json",
        {
            "doctor_name": "Dra. Ana",
            "url": "https://www.doctoralia.com.br/medico/ana",
            "extraction_timestamp": "2026-03-14T09:00:00",
            "reviews": [
                {
                    "id": "a-2",
                    "comment": "Excelente",
                    "rating": 5,
                    "generated_response": "Obrigada.",
                }
            ],
        },
    )

    service = WorkspaceService(tmp_path)
    reports = service.get_reports()

    assert reports["summary"]["total_files"] == 2
    assert reports["summary"]["outdated_snapshots"] == 1
    assert reports["summary"]["generated_current"] == 1
    assert len(reports["cleanup_candidates"]) == 1
    assert reports["cleanup_candidates"][0]["doctor_name"] == "Dra. Ana"
    assert len(reports["inventory"]) == 2
