"""Opt-in PostgreSQL backend end to end on a disposable database (REL-05)."""

import json
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.draft_resolution import list_pending, resolve
from src.db.init_db import drop_db, init_db
from src.db.review_store import (
    PendingDraftConflict,
    StorageRunner,
    approved_drafts,
    load_snapshot_payloads,
    sync_directory,
)
from src.services import storage_backend
from src.services.workspace_service import WorkspaceService

URL = "https://example.test/doctor"


@pytest.fixture
def dsn():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL must identify a disposable database")
    return url


@pytest.fixture
async def database(dsn):
    await drop_db(dsn)
    await init_db(dsn)
    engine = create_async_engine(dsn)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspaces (id,name,slug) VALUES "
                "('ws-rel05','Default','default')"
            )
        )
    try:
        yield engine
    finally:
        await engine.dispose()
        await drop_db(dsn)


def write_snapshot(data_dir, name, day, reviews, status="complete"):
    payload = {
        "doctor_name": "Dra Exemplo",
        "url": URL,
        "extraction_timestamp": f"2026-01-0{day}T12:00:00+00:00",
        "collection": {"status": status, "expected_count": len(reviews)},
        "reviews": reviews,
    }
    (data_dir / name).write_text(json.dumps(payload), encoding="utf-8")


def review(number, draft=None, version=None, date="2026-01-01"):
    item = {
        "id": f"doctoralia:{number}",
        "author": "Paciente",
        "comment": f"Comentário {number}",
        "rating": 5,
        "date": date,
    }
    if draft is not None:
        item["generated_response"] = draft
    if version is not None:
        item["draft_edit"] = {"version": version, "cleared": not draft}
    return item


@pytest.mark.asyncio
async def test_versioned_edits_are_accepted_and_reads_match_json(database, tmp_path):
    write_snapshot(tmp_path, "a.json", 1, [review(1, "Primeiro"), review(2)])
    await sync_directory(database, "ws-rel05", tmp_path)
    # A dashboard edit published with a newer version is not a conflict.
    write_snapshot(
        tmp_path, "b.json", 2, [review(1, "Editado", version=1), review(2), review(3)]
    )
    report = await sync_directory(database, "ws-rel05", tmp_path)
    assert report["reconciled"]["pending"] == 0
    assert (await list_pending(database, "ws-rel05"))["reviews"] == []

    payloads = await load_snapshot_payloads(database, "ws-rel05")
    assert len(payloads) == 2
    latest = payloads[-1]
    drafts = {item["id"]: item["generated_response"] for item in latest["reviews"]}
    assert drafts == {"doctoralia:1": "Editado", "doctoralia:2": "", "doctoralia:3": ""}

    json_view = WorkspaceService(tmp_path).list_pending_responses()
    db_view = WorkspaceService(
        tmp_path, payload_source=lambda: payloads
    ).list_pending_responses()

    def rows(view):
        return sorted(
            (i["review_id"], i["generated_response"] or "", i["date"])
            for i in view["items"]
        )

    assert rows(json_view) == rows(db_view)


@pytest.mark.asyncio
async def test_pending_conflicts_are_withheld_and_block_edits(database, tmp_path):
    write_snapshot(tmp_path, "a.json", 1, [review(1, "Primeiro")])
    write_snapshot(tmp_path, "b.json", 2, [review(1, "Divergente")])
    await sync_directory(database, "ws-rel05", tmp_path)

    latest = (await load_snapshot_payloads(database, "ws-rel05"))[-1]["reviews"][0]
    assert latest["draft_status"] == "pending"
    assert latest["generated_response"] == ""

    from src.db.review_store import save_draft

    with pytest.raises(PendingDraftConflict):
        await save_draft(database, "ws-rel05", URL, "doctoralia:1", "Novo", 9)

    pending = (await list_pending(database, "ws-rel05"))["reviews"][0]
    await resolve(database, "ws-rel05", pending["review_id"], "keep", "ana", 1)
    drafts = await approved_drafts(database, "ws-rel05")
    assert drafts[(URL, "doctoralia:1")] == "Primeiro"

    # Rollback/export: the approved choice reaches the JSON copy.
    exported = storage_backend.export_drafts_to_json(tmp_path, drafts)
    assert exported["updated"] == 1
    newest = json.loads((tmp_path / "b.json").read_text())["reviews"][0]
    assert newest["generated_response"] == "Primeiro"
    # The exported edit is accepted on the next synchronisation.
    report = await sync_directory(database, "ws-rel05", tmp_path)
    assert report["reconciled"]["pending"] >= 0
    assert (await list_pending(database, "ws-rel05"))["reviews"] == []


@pytest.mark.asyncio
async def test_rejected_identities_are_reported_per_run(database, tmp_path):
    legacy = {"id": "7", "comment": "Sem identidade estável", "date": "2026-01-01"}
    write_snapshot(tmp_path, "a.json", 1, [review(1), legacy])
    await sync_directory(database, "ws-rel05", tmp_path)
    (payload,) = await load_snapshot_payloads(database, "ws-rel05")
    assert [item["id"] for item in payload["reviews"]] == ["doctoralia:1"]
    assert payload["collection"]["rejected_reviews"] == 1


def test_dashboard_flow_through_runtime_backend(dsn, tmp_path, monkeypatch):
    import asyncio

    async def prepare():
        await drop_db(dsn)
        await init_db(dsn)
        engine = create_async_engine(dsn)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO workspaces (id,name,slug) VALUES "
                    "('ws-rel05','Default','default')"
                )
            )
        await engine.dispose()

    asyncio.run(prepare())
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", dsn)
    storage_backend.reset()
    try:
        write_snapshot(tmp_path, "a.json", 1, [review(1), review(2)])
        assert storage_backend.sync_after_publish(tmp_path) is not None
        assert storage_backend.status()["last_sync"]["status"] == "ok"

        service = WorkspaceService(
            tmp_path, payload_source=storage_backend.load_snapshot_payloads
        )
        profile_id = service.list_profiles()[0]["profile_id"]
        saved = service.save_generated_response(
            profile_id, "doctoralia:1", "Resposta revisada"
        )
        assert saved is not None
        items = {
            item["review_id"]: item
            for item in service.list_pending_responses()["items"]
        }
        assert items["doctoralia:1"]["generated_response"] == "Resposta revisada"
        assert items["doctoralia:1"]["draft_status"] == "approved"
        on_disk = json.loads((tmp_path / "a.json").read_text())["reviews"][0]
        assert on_disk["generated_response"] == "Resposta revisada"

        # A new collection carrying the edit does not create a conflict.
        write_snapshot(
            tmp_path,
            "b.json",
            2,
            [review(1, "Resposta revisada", version=on_disk["draft_edit"]["version"])],
        )
        report = storage_backend.sync_after_publish(tmp_path)
        assert report["reconciled"]["pending"] == 0

        # Database failures are reported without breaking the JSON publication.
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@127.0.0.1:1/z")
        storage_backend.reset()
        assert storage_backend.sync_after_publish(tmp_path) is None
        assert storage_backend.status()["last_sync"]["status"] == "failed"
    finally:
        storage_backend.reset()
        asyncio.run(drop_db(dsn))


def test_storage_runner_reuses_one_loop(dsn):
    runner = StorageRunner(dsn)

    async def loop_id(_engine):
        import asyncio

        return id(asyncio.get_running_loop())

    try:
        assert runner.run(loop_id) == runner.run(loop_id)
    finally:
        runner.close()


def test_json_backend_is_default(monkeypatch, tmp_path):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    assert storage_backend.backend() == "json"
    assert storage_backend.sync_after_publish(tmp_path) is None
