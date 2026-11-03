import json
import subprocess
import sys
from unittest.mock import patch

import pytest

from src.scraper import DoctoraliaScraper
from src.services.snapshot_storage import snapshot_lock, write_json_atomic
from src.services.workspace_service import WorkspaceService
from tests.fixtures import MockConfig


def test_atomic_write_preserves_old_content_on_failure(tmp_path):
    target = tmp_path / "snapshot.json"
    target.write_text('{"old": true}', encoding="utf-8")

    def fail_after_partial_write(payload, stream, **kwargs):
        stream.write('{"incomplete":')
        raise OSError("disk failure")

    with patch(
        "src.services.snapshot_storage.json.dump", side_effect=fail_after_partial_write
    ):
        with pytest.raises(OSError):
            write_json_atomic(target, {"new": True})
    assert json.loads(target.read_text()) == {"old": True}
    assert not list(tmp_path.glob(".snapshot-*.tmp"))


def test_snapshot_lock_excludes_other_processes(tmp_path):
    code = """
import sys
from filelock import Timeout
from src.services.snapshot_storage import snapshot_lock
try:
    with snapshot_lock(sys.argv[1]).acquire(timeout=0.2):
        sys.exit(0)
except Timeout:
    sys.exit(3)
"""
    with snapshot_lock(tmp_path):
        result = subprocess.run(
            [sys.executable, "-c", code, str(tmp_path)], check=False
        )
        assert result.returncode == 3
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)], check=False)
    assert result.returncode == 0


def test_scraper_saves_distinct_snapshots_for_same_doctor(tmp_path):
    config = MockConfig()
    config.data_dir = tmp_path
    scraper = DoctoraliaScraper(config)
    first = scraper.save_data({"doctor_name": "Dra Ana", "reviews": [{"id": 1}]})
    second = scraper.save_data({"doctor_name": "Dra Ana", "reviews": [{"id": 2}]})
    assert first and second and first != second
    assert json.loads(first.read_text())["reviews"][0]["id"] == 1
    assert json.loads(second.read_text())["reviews"][0]["id"] == 2


def test_direct_scraper_save_preserves_unique_legacy_draft(tmp_path):
    config = MockConfig()
    config.data_dir = tmp_path
    scraper = DoctoraliaScraper(config)
    url = "https://www.doctoralia.com.br/perfil/exemplo"
    old = {
        "doctor_name": "Dra Ana",
        "url": url,
        "extraction_timestamp": "2026-01-01T10:00:00",
        "reviews": [
            {
                "id": 1,
                "author": "Ana",
                "comment": "Ótimo",
                "generated_response": "Obrigada",
            }
        ],
    }
    assert scraper.save_data(old)
    new = {
        "doctor_name": "Dra Ana",
        "url": url,
        "extraction_timestamp": "2026-01-02T10:00:00",
        "reviews": [{"id": "doctoralia:123", "author": "Ana", "comment": "Ótimo"}],
    }
    saved = scraper.save_data(new)
    assert saved
    assert (
        json.loads(saved.read_text())["reviews"][0]["generated_response"] == "Obrigada"
    )


def test_duplicate_review_ids_cannot_receive_ambiguous_edit(tmp_path):
    url = "https://www.doctoralia.com.br/perfil/exemplo"
    payload = {
        "doctor_name": "Dra Ana",
        "url": url,
        "extraction_timestamp": "2026-01-01T10:00:00",
        "reviews": [{"id": "1", "comment": "A"}, {"id": "1", "comment": "B"}],
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(payload))
    service = WorkspaceService(tmp_path)
    profile_id = service.make_profile_id(url, "Dra Ana")
    assert service.save_generated_response(profile_id, "1", "Resposta") is None
    assert json.loads(path.read_text()) == payload


def test_latest_snapshot_supports_mixed_timestamp_formats(tmp_path):
    url = "https://www.doctoralia.com.br/perfil/exemplo"
    common = {"doctor_name": "Dra Ana", "url": url}
    first = {
        **common,
        "extraction_timestamp": "2026-01-01T10:00:00",
        "reviews": [
            {"id": 1, "date": "2026-01-01"},
            {"id": 2, "date": "2026-01-02T10:00:00Z"},
        ],
    }
    second = {**common, "extraction_timestamp": "2026-01-01T12:00:00Z", "reviews": []}
    (tmp_path / "first.json").write_text(json.dumps(first))
    (tmp_path / "second.json").write_text(json.dumps(second))
    service = WorkspaceService(tmp_path)
    snapshots = service._load_snapshots()
    profile_id = service.make_profile_id(url, "Dra Ana")
    assert len(snapshots) == 2
    assert (
        service._latest_by_profile(snapshots)[profile_id]["filename"] == "second.json"
    )
