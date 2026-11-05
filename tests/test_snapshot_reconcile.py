"""End-to-end reconciliation against an explicitly disposable PostgreSQL."""

import asyncio
import hashlib
import json
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.init_db import drop_db, init_db
from src.db.snapshot_import import Candidate, stage_snapshots
from src.db.snapshot_reconcile import reconcile_staged

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def database():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL must identify a disposable database")
    await drop_db(url)
    await init_db(url)
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspaces (id,name,slug) VALUES ('rel01-a','A','rel01-a'),('rel01-b','B','rel01-b')"
            )
        )
    try:
        yield engine
    finally:
        await engine.dispose()


def candidate(reviews, timestamp="2026-01-01T12:00:00+00:00"):
    raw = json.dumps(
        {
            "url": "https://example.test/doctor",
            "doctor_name": "Example",
            "extraction_timestamp": timestamp,
            "collection": {
                "status": "partial",
                "expected_count": 9,
                "stop_reason": "time_limit",
            },
            "reviews": reviews,
        }
    ).encode()
    return Candidate("anonymous.json", hashlib.sha256(raw).hexdigest(), raw, {})


async def test_reconcile_isolated_idempotent_and_auditable(database):
    first = candidate(
        [
            {
                "id": "doctoralia:42",
                "author": "Anonymous",
                "comment": "Example review",
                "rating": 5,
                "date": "2025-12-31",
                "generated_response": "First draft",
            },
            {
                "id": "fingerprint:abc",
                "comment": "No safe identity",
                "generated_response": "Unsafe draft",
            },
            {"id": "doctoralia:7", "comment": "Duplicate one"},
            {"id": "doctoralia:7", "comment": "Duplicate two"},
        ]
    )
    second = candidate(
        [
            {
                "id": "doctoralia:42",
                "comment": "Changed",
                "generated_response": "Conflicting draft",
            }
        ],
        "2026-01-02T12:00:00+00:00",
    )
    await stage_snapshots(database, "rel01-a", [first])
    await stage_snapshots(database, "rel01-a", [second])
    await stage_snapshots(database, "rel01-b", [first])
    reports = await asyncio.gather(
        reconcile_staged(database, "rel01-a"), reconcile_staged(database, "rel01-a")
    )
    assert (
        reports[0]
        == reports[1]
        == {
            "source": 5,
            "imported": 1,
            "duplicates": 1,
            "rejected": 3,
            "pending": 1,
            "snapshots": 2,
        }
    )
    other = await reconcile_staged(database, "rel01-b")
    assert other["imported"] == 1 and other["rejected"] == 3
    async with database.connect() as conn:
        for table, expected in [
            ("profiles", 2),
            ("reviews", 2),
            ("scrape_runs", 3),
            ("review_observations", 3),
            ("review_drafts", 2),
            ("snapshot_rejections", 7),
        ]:
            assert (
                await conn.execute(text(f"SELECT count(*) FROM {table}"))
            ).scalar_one() == expected
        result = (
            await conn.execute(
                text(
                    "SELECT status,expected_count,stop_reason FROM scrape_runs WHERE expected_count=9"
                )
            )
        ).first()
        assert tuple(result) == ("partial", 9, "time_limit")
        assert (
            await conn.execute(
                text(
                    "SELECT count(*) FROM snapshot_imports WHERE sha256=:digest AND original_bytes=:raw"
                ),
                {"digest": first.digest, "raw": first.content},
            )
        ).scalar_one() == 2


async def test_failure_rolls_back_and_can_resume(database, monkeypatch):
    item = candidate([{"id": "doctoralia:99", "comment": "Test"}])
    await stage_snapshots(database, "rel01-a", [item])
    import src.db.snapshot_reconcile as module

    original = module._execute

    async def fail(conn, sql, **params):
        if sql.startswith("INSERT INTO review_observations"):
            raise RuntimeError("injected failure")
        return await original(conn, sql, **params)

    monkeypatch.setattr(module, "_execute", fail)
    with pytest.raises(RuntimeError, match="injected"):
        await reconcile_staged(database, "rel01-a")
    async with database.connect() as conn:
        for table in ("profiles", "reviews", "scrape_runs", "snapshot_reconciliations"):
            assert (
                await conn.execute(text(f"SELECT count(*) FROM {table}"))
            ).scalar_one() == 0
    monkeypatch.setattr(module, "_execute", original)
    assert (await reconcile_staged(database, "rel01-a"))["imported"] == 1
