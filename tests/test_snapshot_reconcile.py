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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "timestamp", ["0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-14:00"]
)
async def test_timestamp_overflow_is_rejected_without_blocking_next_snapshot(
    database, timestamp
):
    review = {"id": "doctoralia:101", "comment": "Synthetic review"}
    await stage_snapshots(database, "rel01-a", [candidate([review], timestamp)])
    await stage_snapshots(database, "rel01-a", [candidate([review])])
    report = await reconcile_staged(database, "rel01-a")
    assert report["snapshots"] == 2
    assert report["rejected"] == 1
    assert report["imported"] == 1
    async with database.connect() as conn:
        reason = (
            await conn.execute(
                text("SELECT reason FROM snapshot_rejections WHERE kind='snapshot'")
            )
        ).scalar_one()
        assert reason == "collection timestamp outside supported UTC range"


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


def changed(item, **values):
    data = json.loads(item.content)
    data.update(values)
    raw = json.dumps(data).encode()
    return Candidate("example.json", hashlib.sha256(raw).hexdigest(), raw, {})


@pytest.mark.asyncio
async def test_draft_chronology_and_incremental_staging(database):
    review = {"id": "doctoralia:1", "comment": "Review"}
    latest = candidate([review], "2026-01-03T12:00:00Z")
    old = candidate([{**review, "generated_response": "Old"}], "2026-01-01T12:00:00Z")
    equal = candidate(
        [{**review, "generated_response": "Equal"}], "2026-01-03T12:00:00Z"
    )
    later = candidate([{**review, "generated_response": "New"}], "2026-01-04T12:00:00Z")
    empty = candidate([{**review, "generated_response": ""}], "2026-01-05T12:00:00Z")
    for item in [latest, old, equal, later, empty]:
        await stage_snapshots(database, "rel01-a", [item])
        await reconcile_staged(database, "rel01-a")
    report = await reconcile_staged(database, "rel01-a")
    assert report["snapshots"] == 5
    async with database.connect() as conn:
        assert (
            await conn.execute(text("SELECT count(*) FROM review_drafts"))
        ).scalar_one() == 0
        state = (
            await conn.execute(
                text("SELECT observed_at,body FROM snapshot_draft_state")
            )
        ).one()
        assert state.body is None and state.observed_at.day == 5
        assert (
            await conn.execute(
                text("SELECT count(*) FROM snapshot_rejections WHERE kind='draft'")
            )
        ).scalar_one() >= 3


@pytest.mark.asyncio
async def test_dates_invalid_input_and_following_snapshot(database):
    reviews = [
        {
            "id": f"doctoralia:{i}",
            "comment": "Review",
            "date": value,
            "generated_response": "Draft",
        }
        for i, value in enumerate(
            [
                "2026-01-02T23:59:00Z",
                "2026-01-03T00:30:00+03:00",
                "2026-01-04",
                "invalid",
            ],
            1,
        )
    ]
    reviews.append(
        {
            "id": "doctoralia:9",
            "comment": "bad\u0000text",
            "generated_response": "Keep me",
        }
    )
    reviews.append(
        {"id": "doctoralia:10", "comment": "valid", "extra": {"bad": "\u0000"}}
    )
    bad_count = changed(candidate(reviews), collection={"expected_count": 2147483648})
    bad_nul = changed(candidate(reviews), doctor_name="Bad\u0000name")
    valid = candidate(reviews)
    await stage_snapshots(database, "rel01-a", [bad_count, bad_nul, valid])
    report = await reconcile_staged(database, "rel01-a")
    assert report["imported"] == 3 and report["rejected"] == 15
    async with database.connect() as conn:
        dates = (
            (
                await conn.execute(
                    text("SELECT reviewed_at FROM reviews ORDER BY source_id")
                )
            )
            .scalars()
            .all()
        )
        assert [d.isoformat() for d in dates] == [
            "2026-01-02",
            "2026-01-03",
            "2026-01-04",
        ]
        assert (
            await conn.execute(text("SELECT count(*) FROM review_drafts"))
        ).scalar_one() == 3
        assert (
            await conn.execute(
                text("SELECT count(*) FROM snapshot_imports WHERE original_bytes=:raw"),
                {"raw": valid.content},
            )
        ).scalar_one() == 1


@pytest.mark.asyncio
async def test_profile_equivalence_and_naive_time_rejection(database):
    review = [
        {"id": "doctoralia:1", "comment": "Review", "generated_response": "Draft"}
    ]
    first = candidate(review)
    spaced = changed(
        candidate(review, "2026-01-02T12:00:00Z"), url="  https://example.test/doctor  "
    )
    other = changed(
        candidate(review, "2026-01-03T12:00:00Z"), url="https://example.test/other"
    )
    ambiguous = changed(
        candidate(review, "2026-01-04T12:00:00Z"), url="https://example.test/Doctor"
    )
    naive = candidate(review, "2026-01-05T12:00:00")
    await stage_snapshots(database, "rel01-a", [first])
    await reconcile_staged(database, "rel01-a")
    await stage_snapshots(database, "rel01-a", [spaced, other, ambiguous, naive])
    await stage_snapshots(database, "rel01-b", [spaced])
    result = await reconcile_staged(database, "rel01-a")
    await reconcile_staged(database, "rel01-b")
    assert (
        result["imported"] == 2
        and result["duplicates"] == 1
        and result["rejected"] == 2
    )
    async with database.connect() as conn:
        assert (
            await conn.execute(text("SELECT count(*) FROM profiles"))
        ).scalar_one() == 3
        reasons = (
            (
                await conn.execute(
                    text("SELECT reason FROM snapshot_rejections WHERE kind='snapshot'")
                )
            )
            .scalars()
            .all()
        )
        assert "ambiguous profile URL" in reasons
        assert "collection timestamp has no timezone" in reasons


@pytest.mark.asyncio
async def test_draft_absence_conflict_when_older_arrives_first(database):
    review = {"id": "doctoralia:22", "comment": "Review"}
    before = candidate(
        [{**review, "generated_response": "Preserved"}], "2026-01-01T12:00:00Z"
    )
    after = candidate([review], "2026-01-02T12:00:00Z")
    await stage_snapshots(database, "rel01-a", [before])
    await reconcile_staged(database, "rel01-a")
    await stage_snapshots(database, "rel01-a", [after])
    assert (await reconcile_staged(database, "rel01-a"))["pending"] == 1
    async with database.connect() as conn:
        assert (
            await conn.execute(text("SELECT body FROM review_drafts"))
        ).scalar_one() == "Preserved"
        assert (
            await conn.execute(text("SELECT body FROM snapshot_draft_state"))
        ).scalar_one() is None
        assert (
            await conn.execute(
                text("SELECT reason FROM snapshot_rejections WHERE kind='draft'")
            )
        ).scalar_one() == "conflicting draft observations"


@pytest.mark.asyncio
async def test_naive_and_aware_times_and_invalid_counts(database):
    review = [
        {"id": "doctoralia:77", "comment": "Review", "generated_response": "Preserve"}
    ]
    naive = candidate(review, "2026-01-01T12:00:00")
    aware = candidate(review, "2026-01-02T12:00:00-03:00")
    invalid_count = changed(
        candidate(review, "2026-01-03T12:00:00Z"),
        collection={"extracted_count": 2147483648},
    )
    await stage_snapshots(database, "rel01-a", [naive, aware, invalid_count])
    report = await reconcile_staged(database, "rel01-a")
    assert (report["imported"], report["rejected"]) == (1, 2)
    async with database.connect() as conn:
        assert (
            await conn.execute(text("SELECT body FROM review_drafts"))
        ).scalar_one() == "Preserve"
        assert (
            await conn.execute(text("SELECT count(*) FROM snapshot_imports"))
        ).scalar_one() == 3


def test_cli_uses_workspace_and_reports(monkeypatch, capsys):
    import sys

    import src.db.snapshot_reconcile as module

    class FakeEngine:
        async def dispose(self):
            pass

    async def fake_reconcile(engine, workspace):
        assert workspace == "workspace"
        return {"snapshots": 3}

    monkeypatch.setattr(module, "database_url", lambda: "unused")
    monkeypatch.setattr(
        module, "create_async_engine", lambda *args, **kwargs: FakeEngine()
    )
    monkeypatch.setattr(module, "reconcile_staged", fake_reconcile)
    monkeypatch.setattr(
        sys, "argv", ["snapshot_reconcile", "--workspace-id", "workspace"]
    )
    module.main()
    assert json.loads(capsys.readouterr().out) == {"snapshots": 3}


def test_timestamp_and_date_validation():
    from src.db.snapshot_reconcile import _date, _timestamp

    for invalid in (None, "bad", "2026-01-01T12:00:00"):
        with pytest.raises(ValueError):
            _timestamp(invalid)
    assert _timestamp("2026-01-01T01:00:00+01:00").hour == 0
    assert _date(None) is None
    for invalid in (42, "no date"):
        with pytest.raises(ValueError):
            _date(invalid)


@pytest.mark.asyncio
async def test_pre_migration_observations_do_not_resurrect_draft(database):
    review = {"id": "doctoralia:33", "comment": "Review"}
    latest = candidate([review], "2026-01-02T12:00:00Z")
    older = candidate([{**review, "generated_response": "Old"}], "2026-01-01T12:00:00Z")
    await stage_snapshots(database, "rel01-a", [latest])
    await reconcile_staged(database, "rel01-a")
    async with database.begin() as conn:
        await conn.execute(text("DELETE FROM snapshot_draft_state"))
    await stage_snapshots(database, "rel01-a", [older])
    assert (await reconcile_staged(database, "rel01-a"))["pending"] == 1
    async with database.connect() as conn:
        assert (
            await conn.execute(text("SELECT count(*) FROM review_drafts"))
        ).scalar_one() == 0
        assert (
            await conn.execute(
                text("SELECT reason FROM snapshot_rejections WHERE kind='draft'")
            )
        ).scalar_one() == "unknown earlier draft provenance"
