"""Auditable resolution of imported draft conflicts on a disposable PostgreSQL."""

import asyncio
import hashlib
import json
import os

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.draft_resolution import (
    ResolutionError,
    StaleDecisionError,
    draft_for_review,
    list_pending,
    main,
    resolve,
)
from src.db.init_db import _migration_config, drop_db, init_db
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
                "INSERT INTO workspaces (id,name,slug) VALUES "
                "('rel03-a','A','rel03-a'),('rel03-b','B','rel03-b')"
            )
        )
    try:
        yield engine
    finally:
        await engine.dispose()


def candidate(draft, day):
    raw = json.dumps(
        {
            "url": "https://example.test/doctor",
            "doctor_name": "Example",
            "extraction_timestamp": f"2026-01-0{day}T12:00:00+00:00",
            "collection": {"status": "complete"},
            "reviews": [
                {
                    "id": "doctoralia:42",
                    "comment": "Synthetic review",
                    "generated_response": draft,
                }
            ],
        }
    ).encode()
    return Candidate(f"day{day}.json", hashlib.sha256(raw).hexdigest(), raw, {})


async def import_drafts(engine, workspace, *drafts, start=1):
    for offset, draft in enumerate(drafts):
        await stage_snapshots(engine, workspace, [candidate(draft, start + offset)])
    return await reconcile_staged(engine, workspace)


async def only_review(engine, workspace="rel03-a"):
    listing = await list_pending(engine, workspace)
    assert len(listing["reviews"]) == 1
    return listing["reviews"][0]


@pytest.mark.asyncio
async def test_conflict_is_pending_until_an_explicit_audited_decision(database):
    report = await import_drafts(database, "rel03-a", "First draft", "Second draft")
    assert report["pending"] == 1

    review = await only_review(database)
    assert review["current_draft"] == "First draft"
    assert review["revision"] == 1
    assert review["status"] == "pending"
    assert [item["draft"] for item in review["observations"]] == [
        "First draft",
        "Second draft",
    ]
    (conflict,) = review["pending"]
    assert conflict["proposed_body"] == "Second draft"

    async with database.connect() as conn:
        draft = await draft_for_review(conn, review["review_id"])
    assert draft["status"] == "pending"
    assert draft["body"] is None
    assert draft["pending_body"] == "First draft"

    with pytest.raises(StaleDecisionError):
        await resolve(
            database,
            "rel03-a",
            review["review_id"],
            "choose",
            "operator",
            expected_revision=0,
            rejection_id=conflict["rejection_id"],
        )

    result = await resolve(
        database,
        "rel03-a",
        review["review_id"],
        "choose",
        "operator",
        expected_revision=1,
        rejection_id=conflict["rejection_id"],
        note="newer wording approved",
    )
    assert result["resolved_body"] == "Second draft"
    assert result["revision"] == 2
    assert (await list_pending(database, "rel03-a"))["reviews"] == []

    async with database.connect() as conn:
        draft = await draft_for_review(conn, review["review_id"])
        audit = (
            await conn.execute(
                text(
                    "SELECT decision, actor, previous_body, resolved_body, note, "
                    "expected_revision, resulting_revision FROM draft_resolutions"
                )
            )
        ).one()
    assert draft == {
        "status": "approved",
        "body": "Second draft",
        "revision": 2,
        "pending_conflicts": 0,
    }
    assert tuple(audit) == (
        "choose",
        "operator",
        "First draft",
        "Second draft",
        "newer wording approved",
        1,
        2,
    )

    with pytest.raises(ResolutionError):
        await resolve(database, "rel03-a", review["review_id"], "keep", "operator", 2)


@pytest.mark.asyncio
async def test_new_conflicting_observation_reopens_and_clear_is_recorded(database):
    await import_drafts(database, "rel03-a", "First draft", "Second draft")
    review = await only_review(database)
    await resolve(database, "rel03-a", review["review_id"], "keep", "ana", 1)

    await import_drafts(database, "rel03-a", "Third draft", start=3)
    reopened = await only_review(database)
    assert reopened["revision"] == 2
    assert [item["proposed_body"] for item in reopened["pending"]] == ["Third draft"]
    assert [item["decision"] for item in reopened["resolutions"]] == ["keep"]

    cleared = await resolve(database, "rel03-a", review["review_id"], "clear", "bia", 2)
    assert cleared["resolved_body"] is None
    async with database.connect() as conn:
        draft = await draft_for_review(conn, review["review_id"])
        rows = (
            await conn.execute(
                text("SELECT count(*) FROM review_drafts WHERE review_id=:id"),
                {"id": review["review_id"]},
            )
        ).scalar_one()
    assert rows == 0
    assert draft == {
        "status": "absent",
        "body": None,
        "revision": 3,
        "pending_conflicts": 0,
    }


@pytest.mark.asyncio
async def test_concurrent_decisions_on_same_revision_apply_exactly_once(database):
    await import_drafts(database, "rel03-a", "First draft", "Second draft")
    review = await only_review(database)
    results = await asyncio.gather(
        resolve(database, "rel03-a", review["review_id"], "keep", "ana", 1),
        resolve(database, "rel03-a", review["review_id"], "clear", "bia", 1),
        return_exceptions=True,
    )
    assert sum(isinstance(item, dict) for item in results) == 1
    assert sum(isinstance(item, StaleDecisionError) for item in results) == 1
    async with database.connect() as conn:
        count = (
            await conn.execute(text("SELECT count(*) FROM draft_resolutions"))
        ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_decisions_are_validated_and_workspace_isolated(database):
    await import_drafts(database, "rel03-a", "First draft", "Second draft")
    await import_drafts(database, "rel03-b", "Other", "Other changed")
    review = await only_review(database)
    other = await only_review(database, "rel03-b")

    with pytest.raises(ResolutionError):
        await resolve(database, "rel03-b", review["review_id"], "keep", "ana", 1)
    with pytest.raises(ResolutionError):
        await resolve(
            database,
            "rel03-a",
            review["review_id"],
            "choose",
            "ana",
            1,
            rejection_id=other["pending"][0]["rejection_id"],
        )
    with pytest.raises(ResolutionError):
        await resolve(database, "rel03-a", review["review_id"], "keep", "  ", 1)
    with pytest.raises(ResolutionError):
        await resolve(database, "rel03-a", review["review_id"], "approve", "ana", 1)
    with pytest.raises(ResolutionError):
        await resolve(database, "rel03-a", review["review_id"], "choose", "ana", 1)
    with pytest.raises(ResolutionError):
        await list_pending(database, "missing-workspace")

    assert (await only_review(database))["status"] == "pending"


@pytest.mark.asyncio
async def test_resolution_history_is_append_only(database):
    await import_drafts(database, "rel03-a", "First draft", "Second draft")
    review = await only_review(database)
    await resolve(database, "rel03-a", review["review_id"], "keep", "ana", 1)
    for statement in (
        "UPDATE draft_resolutions SET actor='mallory'",
        "DELETE FROM draft_resolutions",
    ):
        with pytest.raises(DBAPIError):
            async with database.begin() as conn:
                await conn.execute(text(statement))


@pytest.mark.asyncio
async def test_upgrade_links_existing_conflicts_without_guessing(database):
    await import_drafts(database, "rel03-a", "First draft", "Second draft")
    review = await only_review(database)
    async with database.begin() as conn:
        await conn.run_sync(
            lambda connection: command.downgrade(
                _migration_config(connection), "0005_repair_draft_provenance"
            )
        )
        snapshot = (
            await conn.execute(text("SELECT snapshot_id FROM snapshot_rejections"))
        ).scalar_one()
        for rejection_id, payload in (
            ("legacy-marker", {"review_id": review["review_id"]}),
            ("unknown-identity", {"id": "fingerprint:abc", "generated_response": "x"}),
        ):
            await conn.execute(
                text(
                    "INSERT INTO snapshot_rejections (id,snapshot_id,kind,reason,payload) "
                    "VALUES (:id,:snapshot,'draft','synthetic',CAST(:payload AS JSON))"
                ),
                {
                    "id": rejection_id,
                    "snapshot": snapshot,
                    "payload": json.dumps(payload),
                },
            )
        await conn.run_sync(
            lambda connection: command.upgrade(_migration_config(connection), "head")
        )

    listing = await list_pending(database, "rel03-a")
    (linked,) = listing["reviews"]
    assert len(linked["pending"]) == 2
    assert [item["rejection_id"] for item in listing["unlinked"]] == [
        "unknown-identity"
    ]


@pytest.mark.asyncio
async def test_cli_lists_and_reports_stale_decisions(database, monkeypatch, capsys):
    await import_drafts(database, "rel03-a", "First draft", "Second draft")
    review = await only_review(database)
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_POSTGRES_URL"])

    await asyncio.to_thread(main, ["list", "--workspace-id", "rel03-a"])
    listed = json.loads(capsys.readouterr().out)
    assert listed["reviews"][0]["review_id"] == review["review_id"]

    with pytest.raises(SystemExit) as exit_info:
        await asyncio.to_thread(
            main,
            [
                "resolve",
                "--workspace-id",
                "rel03-a",
                "--review-id",
                review["review_id"],
                "--decision",
                "keep",
                "--actor",
                "ana",
                "--expected-revision",
                "7",
            ],
        )
    assert exit_info.value.code == 2
    assert "draft revision is 1" in capsys.readouterr().err
