"""Repair already-reconciled legacy data using real Alembic upgrades."""

import asyncio
import hashlib
import json
import os
from datetime import datetime

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.init_db import _migration_config, drop_db, init_db
from src.db.snapshot_import import Candidate, stage_snapshots
from src.db.snapshot_reconcile import reconcile_staged


@pytest.fixture
async def legacy_database():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL must identify a disposable database")
    await drop_db(url)
    await init_db(url)
    engine = create_async_engine(url)
    try:
        yield engine, url
    finally:
        await engine.dispose()


async def seed_legacy(engine, revision, reverse=False, naive=False):
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda connection: command.downgrade(
                _migration_config(connection), revision
            )
        )
        for workspace in ("legacy-a", "legacy-b"):
            await conn.execute(
                text("INSERT INTO workspaces (id,name,slug) VALUES (:id,:id,:id)"),
                {"id": workspace},
            )
            await conn.execute(
                text(
                    "INSERT INTO profiles (id,workspace_id,source_url,name) VALUES (:id,:w,'https://example.test/legacy','Synthetic')"
                ),
                {"id": workspace + "-profile", "w": workspace},
            )
            for suffix in ("cleared", "stable"):
                review_id = workspace + "-" + suffix
                source_id = "doctoralia:1" if suffix == "cleared" else "doctoralia:2"
                await conn.execute(
                    text(
                        "INSERT INTO reviews (id,profile_id,source_id,identity_status,body) VALUES (:id,:p,:s,'source','Synthetic')"
                    ),
                    {"id": review_id, "p": workspace + "-profile", "s": source_id},
                )
                await conn.execute(
                    text(
                        "INSERT INTO review_drafts (review_id,body) VALUES (:id,:body)"
                    ),
                    {"id": review_id, "body": "A" if suffix == "cleared" else "same"},
                )
    for workspace in ("legacy-a", "legacy-b"):
        days = (2, 1) if reverse else (1, 2)
        snapshot_ids = {}
        for day in days:
            reviews = [
                {"id": "doctoralia:1", "comment": "Synthetic"},
                {
                    "id": "doctoralia:2",
                    "comment": "Synthetic",
                    "generated_response": "same",
                },
            ]
            if day == 1:
                reviews[0]["generated_response"] = "A"
            timestamp = f"2026-01-0{day}T12:00:00+00:00"
            raw = json.dumps(
                {
                    "url": "https://example.test/legacy",
                    "extraction_timestamp": timestamp[:19] if naive else timestamp,
                    "reviews": reviews,
                }
            ).encode()
            digest = hashlib.sha256(raw).hexdigest()
            await stage_snapshots(
                engine, workspace, [Candidate(f"day-{day}.json", digest, raw, {})]
            )
            async with engine.begin() as conn:
                snapshot_id = (
                    await conn.execute(
                        text(
                            "SELECT id FROM snapshot_imports WHERE workspace_id=:w AND sha256=:s"
                        ),
                        {"w": workspace, "s": digest},
                    )
                ).scalar_one()
                snapshot_ids[day] = snapshot_id
                run_id = workspace + f"-run-{day}"
                await conn.execute(
                    text(
                        "INSERT INTO scrape_runs (id,profile_id,status,started_at,finished_at) VALUES (:id,:p,'complete',CAST(:ts AS TIMESTAMPTZ),CAST(:ts AS TIMESTAMPTZ))"
                    ),
                    {
                        "id": run_id,
                        "p": workspace + "-profile",
                        "ts": datetime.fromisoformat(timestamp),
                    },
                )
                for suffix, payload in zip(("cleared", "stable"), reviews):
                    await conn.execute(
                        text(
                            "INSERT INTO review_observations (run_id,review_id,profile_id,payload) VALUES (:run,:review,:profile,CAST(:payload AS JSON))"
                        ),
                        {
                            "run": run_id,
                            "review": workspace + "-" + suffix,
                            "profile": workspace + "-profile",
                            "payload": json.dumps(payload),
                        },
                    )
                report = {
                    "source": 2,
                    "imported": 2 if day == 1 else 0,
                    "duplicates": 0 if day == 1 else 2,
                    "rejected": 0,
                    "pending": 1 if workspace == "legacy-b" and day == 2 else 0,
                }
                await conn.execute(
                    text(
                        "INSERT INTO snapshot_reconciliations (snapshot_id,run_id,report) VALUES (:id,:run,CAST(:report AS JSON))"
                    ),
                    {"id": snapshot_id, "run": run_id, "report": json.dumps(report)},
                )
        async with engine.begin() as conn:
            if workspace == "legacy-b":
                await conn.execute(
                    text(
                        "INSERT INTO snapshot_rejections (id,snapshot_id,kind,reason,payload) VALUES ('existing-conflict',:snapshot,'draft','existing conflict',CAST(:payload AS JSON))"
                    ),
                    {
                        "snapshot": snapshot_ids[2],
                        "payload": json.dumps({"id": "doctoralia:1"}),
                    },
                )
            if revision == "0004_snapshot_draft_state":
                await conn.execute(
                    text(
                        "INSERT INTO snapshot_draft_state (review_id,snapshot_id,observed_at,body) VALUES (:review,:snapshot,'2026-01-02T12:00:00Z','same')"
                    ),
                    {"review": workspace + "-stable", "snapshot": snapshot_ids[2]},
                )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "revision", ["0003_snapshot_reconciliation", "0004_snapshot_draft_state"]
)
@pytest.mark.parametrize("reverse", [False, True])
async def test_upgrade_recovers_states_conflicts_and_reports(
    legacy_database, revision, reverse
):
    engine, url = legacy_database
    await seed_legacy(engine, revision, reverse)
    await init_db(url)
    await asyncio.gather(init_db(url), init_db(url))
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda connection: command.downgrade(
                _migration_config(connection), "0004_snapshot_draft_state"
            )
        )
    await init_db(url)
    async with engine.connect() as conn:
        states = (
            await conn.execute(text("SELECT review_id,body FROM snapshot_draft_state"))
        ).all()
        assert dict(states) == {
            "legacy-a-cleared": None,
            "legacy-a-stable": "same",
            "legacy-b-cleared": None,
            "legacy-b-stable": "same",
        }
        assert (
            await conn.execute(text("SELECT count(*) FROM snapshot_rejections"))
        ).scalar_one() == 2
        assert (
            await conn.execute(text("SELECT count(*) FROM review_drafts"))
        ).scalar_one() == 4
        assert (
            await conn.execute(text("SELECT count(*) FROM snapshot_imports"))
        ).scalar_one() == 4
        repaired = (
            await conn.execute(
                text(
                    "SELECT payload FROM snapshot_rejections WHERE reason='legacy draft provenance requires review'"
                )
            )
        ).scalar_one()
        assert repaired["review_id"] == "legacy-a-cleared"
        assert repaired["requires_human_resolution"] is True
    for workspace in ("legacy-a", "legacy-b"):
        first = await reconcile_staged(engine, workspace)
        assert first["pending"] == 1
        assert first["snapshots"] == 2
        assert await reconcile_staged(engine, workspace) == first


@pytest.mark.asyncio
async def test_upgrade_failure_rolls_back_and_can_resume(legacy_database):
    engine, url = legacy_database
    await seed_legacy(engine, "0004_snapshot_draft_state")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE FUNCTION fail_legacy_repair() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected upgrade failure'; END $$"
            )
        )
        await conn.execute(
            text(
                "CREATE TRIGGER fail_legacy_repair BEFORE INSERT ON snapshot_rejections FOR EACH ROW EXECUTE FUNCTION fail_legacy_repair()"
            )
        )
    with pytest.raises(Exception, match="injected upgrade failure"):
        await init_db(url)
    async with engine.begin() as conn:
        assert (
            await conn.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one() == "0004_snapshot_draft_state"
        assert (
            await conn.execute(text("SELECT count(*) FROM snapshot_draft_state"))
        ).scalar_one() == 2
        assert (
            await conn.execute(text("SELECT count(*) FROM snapshot_rejections"))
        ).scalar_one() == 1
        await conn.execute(
            text("DROP TRIGGER fail_legacy_repair ON snapshot_rejections")
        )
        await conn.execute(text("DROP FUNCTION fail_legacy_repair()"))
    await init_db(url)
    assert (await reconcile_staged(engine, "legacy-a"))["pending"] == 1


@pytest.mark.asyncio
async def test_legacy_naive_times_remain_explicitly_uncertain(legacy_database):
    engine, url = legacy_database
    await seed_legacy(engine, "0004_snapshot_draft_state", naive=True)
    await init_db(url)
    for workspace in ("legacy-a", "legacy-b"):
        assert (await reconcile_staged(engine, workspace))["pending"] == 2
    async with engine.connect() as conn:
        payloads = (
            (
                await conn.execute(
                    text(
                        "SELECT payload FROM snapshot_rejections WHERE reason='legacy draft provenance requires review'"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(payloads) == 3
        assert all(payload["time_uncertain"] for payload in payloads)


@pytest.mark.asyncio
async def test_incomplete_observation_payload_is_not_approved(legacy_database):
    engine, url = legacy_database
    await seed_legacy(engine, "0003_snapshot_reconciliation")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE review_observations SET payload='null' WHERE review_id='legacy-a-stable'"
            )
        )
        await conn.execute(
            text("DELETE FROM review_drafts WHERE review_id='legacy-a-stable'")
        )
    await init_db(url)
    assert (await reconcile_staged(engine, "legacy-a"))["pending"] == 2
