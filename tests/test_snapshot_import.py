"""Safety and idempotence checks for snapshot staging."""

import argparse
import hashlib
import json

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.base import Base
from src.db.init_db import _migration_config, init_db
from src.db.snapshot_import import (
    backup_snapshots,
    inspect_snapshots,
    main,
    run,
    stage_snapshots,
)


def snapshot(reviews):
    return {
        "doctor_name": "Test",
        "url": "https://example.com/profile",
        "extraction_timestamp": "2026-01-01T00:00:00",
        "reviews": reviews,
    }


def test_cli_returns_nonzero_when_any_snapshot_is_rejected(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / "invalid.json").write_text("not json")
    monkeypatch.setattr("sys.argv", ["snapshot_import", "--data-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert (
        json.loads(capsys.readouterr().out)["rejected"][0]["reason"] == "invalid JSON"
    )


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        ({"reviews": "not a list"}, "not a snapshot"),
        ({"reviews": []}, "missing collection timestamp"),
        ({"reviews": [], "scraped_at": "2026-01-01"}, "missing profile URL"),
        (
            {
                "reviews": ["not a review"],
                "scraped_at": "2026-01-01",
                "url": "https://example.com",
            },
            "invalid review entry",
        ),
    ],
)
def test_invalid_snapshot_structure_is_reported_without_import(tmp_path, data, reason):
    (tmp_path / "bad.json").write_text(json.dumps(data))
    candidates, rejected = inspect_snapshots(tmp_path)
    assert not candidates
    assert rejected == [{"filename": "bad.json", "reason": reason}]


def test_snapshot_directory_must_exist(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        inspect_snapshots(tmp_path / "missing")


@pytest.mark.asyncio
async def test_apply_rejects_snapshot_directory_as_backup(tmp_path):
    args = argparse.Namespace(
        data_dir=str(tmp_path), apply=True, workspace_id="w", backup_dir=str(tmp_path)
    )
    with pytest.raises(ValueError, match="Backup directory must differ"):
        await run(args)


@pytest.mark.asyncio
async def test_upgrade_from_first_revision_preserves_existing_data(tmp_path):
    dsn = f"sqlite+aiosqlite:///{tmp_path / 'old.db'}"
    engine = create_async_engine(dsn)

    def initialize_first_revision(connection):
        Base.metadata.create_all(connection)
        command.upgrade(_migration_config(connection), "0001_review_storage")
        connection.execute(
            text(
                "INSERT INTO workspaces (id, name, slug) VALUES ('w', 'Existing', 'existing')"
            )
        )

    async with engine.begin() as connection:
        await connection.run_sync(initialize_first_revision)
    await init_db(dsn)
    async with engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT name FROM workspaces WHERE id = 'w'"))
        ).scalar_one() == "Existing"
        assert (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one() == "0003_snapshot_reconciliation"
    await engine.dispose()


@pytest.mark.asyncio
async def test_inspection_dry_run_and_transactional_idempotent_staging(tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    original = json.dumps(
        snapshot(
            [
                {"id": 1, "comment": "Test"},
                {"id": "doctoralia:5"},
                {"id": "doctoralia:5"},
            ]
        )
    ).encode()
    (source / "a.json").write_bytes(original)
    (source / "duplicate.json").write_bytes(original)
    (source / "invalid.json").write_text("not json")
    report = await run(
        argparse.Namespace(
            data_dir=str(source), apply=False, workspace_id=None, backup_dir=None
        )
    )
    assert report["mode"] == "dry-run"
    assert len(report["rejected"]) == 1
    assert report["files"][0]["issues"]["duplicate_source_ids"] == 2
    assert report["files"][0]["issues"]["legacy_or_missing_ids"] == 1
    assert (source / "a.json").read_bytes() == original

    candidates, _ = inspect_snapshots(source)
    backups = tmp_path / "backups"
    backup_snapshots(candidates, backups)
    backup = backups / (hashlib.sha256(original).hexdigest() + ".snapshot")
    assert backup.read_bytes() == original
    backup_snapshots(candidates, backups)

    dsn = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    await init_db(dsn)
    engine = create_async_engine(dsn)
    async with engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO workspaces (id, name, slug) VALUES ('w', 'Test', 'test')")
        )
    assert await stage_snapshots(engine, "w", candidates) == {
        "inserted": 1,
        "duplicates": 1,
    }
    assert await stage_snapshots(engine, "w", candidates) == {
        "inserted": 0,
        "duplicates": 2,
    }
    async with engine.connect() as connection:
        stored = (
            await connection.execute(
                text("SELECT original_bytes, issue_summary FROM snapshot_imports")
            )
        ).one()
        assert stored[0] == original
        assert json.loads(stored[1])["duplicate_source_ids"] == 2
    with pytest.raises(ValueError, match="Workspace"):
        await stage_snapshots(engine, "missing", candidates)
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE snapshot_imports SET original_bytes = :content"),
            {"content": b"corrupted"},
        )
    (source / "new.json").write_text(json.dumps(snapshot([{"id": "doctoralia:8"}])))
    updated, _ = inspect_snapshots(source)
    ordered = [
        next(item for item in updated if item.filename == "new.json"),
        candidates[0],
    ]
    with pytest.raises(ValueError, match="Stored snapshot"):
        await stage_snapshots(engine, "w", ordered)
    async with engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT count(*) FROM snapshot_imports"))
        ).scalar_one() == 1
    await engine.dispose()


def test_backup_refuses_mismatched_existing_copy(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.json").write_text(json.dumps(snapshot([])))
    candidates, _ = inspect_snapshots(source)
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / (candidates[0].digest + ".snapshot")).write_text("wrong")
    with pytest.raises(ValueError, match="checksum"):
        backup_snapshots(candidates, backups)


@pytest.mark.asyncio
async def test_apply_requires_backup_and_stages_without_changing_original(
    tmp_path, monkeypatch
):
    source = tmp_path / "source"
    source.mkdir()
    original = json.dumps(snapshot([])).encode()
    (source / "a.json").write_bytes(original)
    dsn = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    await init_db(dsn)
    engine = create_async_engine(dsn)
    async with engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO workspaces (id, name, slug) VALUES ('w', 'Test', 'test')")
        )
    await engine.dispose()
    monkeypatch.setenv("DATABASE_URL", dsn)
    args = argparse.Namespace(
        data_dir=str(source), apply=True, workspace_id="w", backup_dir=None
    )
    with pytest.raises(ValueError, match="backup-dir"):
        await run(args)
    args.backup_dir = str(tmp_path / "backup")
    report = await run(args)
    assert report["inserted"] == 1
    assert (source / "a.json").read_bytes() == original
    assert (
        tmp_path / "backup" / (hashlib.sha256(original).hexdigest() + ".snapshot")
    ).read_bytes() == original
