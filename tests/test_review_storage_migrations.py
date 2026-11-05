"""Integration checks for the versioned review-storage schema."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.base import Base
from src.db.init_db import drop_db, init_db
from src.db.snapshot_import import Candidate, stage_snapshots


@pytest.mark.asyncio
async def test_upgrade_preserves_existing_workspace_and_is_idempotent(tmp_path):
    dsn = f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}"
    engine = create_async_engine(dsn)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            text(
                "INSERT INTO workspaces (id, name, slug) VALUES ('w', 'Existing', 'existing')"
            )
        )

    await init_db(dsn)
    await init_db(dsn)

    async with engine.connect() as connection:
        tables = await connection.run_sync(
            lambda conn: set(inspect(conn).get_table_names())
        )
        assert {
            "profiles",
            "reviews",
            "scrape_runs",
            "review_observations",
            "review_drafts",
            "alembic_version",
        } <= tables
        assert (
            await connection.execute(text("SELECT name FROM workspaces WHERE id = 'w'"))
        ).scalar_one() == "Existing"
        assert (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one() == "0007_draft_edit_version"
    await drop_db(dsn)
    async with engine.connect() as connection:
        tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        assert not tables
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_enforces_review_identity_and_profile_isolation():
    dsn = os.environ.get("TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("TEST_POSTGRES_URL must point to a disposable PostgreSQL database")
    engine = create_async_engine(dsn)
    async with engine.connect() as connection:
        tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        assert (
            not tables
        ), "TEST_POSTGRES_URL must point to an empty disposable database"
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            text(
                "INSERT INTO workspaces (id, name, slug) VALUES ('legacy', 'Existing', 'existing')"
            )
        )
    await init_db(dsn)
    await init_db(dsn)
    async with engine.connect() as connection:
        assert (
            await connection.execute(
                text("SELECT name FROM workspaces WHERE id = 'legacy'")
            )
        ).scalar_one() == "Existing"
    workspace, profile_a, profile_b, review, run = (str(uuid4()) for _ in range(5))
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO workspaces (id, name, slug) VALUES (:id, 'Test', 'test')"
            ),
            {"id": workspace},
        )
        await connection.execute(
            text(
                "INSERT INTO profiles (id, workspace_id, source_url, name) VALUES (:a, :w, 'https://a', 'A'), (:b, :w, 'https://b', 'B')"
            ),
            {"a": profile_a, "b": profile_b, "w": workspace},
        )
        await connection.execute(
            text(
                "INSERT INTO reviews (id, profile_id, source_id, identity_status, body) VALUES (:id, :profile, '123', 'source', 'Review')"
            ),
            {"id": review, "profile": profile_a},
        )
        await connection.execute(
            text(
                "INSERT INTO scrape_runs (id, profile_id, status, started_at) VALUES (:id, :profile, 'complete', CURRENT_TIMESTAMP)"
            ),
            {"id": run, "profile": profile_b},
        )
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO review_observations (run_id, review_id, profile_id, payload) VALUES (:run, :review, :profile, '{}')"
                ),
                {"run": run, "review": review, "profile": profile_b},
            )
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO reviews (id, profile_id, source_id, identity_status, body) VALUES (:id, :profile, '123', 'source', 'Duplicate')"
                ),
                {"id": str(uuid4()), "profile": profile_a},
            )
    candidate = Candidate(
        "test.json", "a" * 64, b'{"reviews":[]}', {"ambiguous_ids": 0}
    )
    assert await stage_snapshots(engine, workspace, [candidate]) == {
        "inserted": 1,
        "duplicates": 0,
    }
    assert await stage_snapshots(engine, workspace, [candidate]) == {
        "inserted": 0,
        "duplicates": 1,
    }
    async with engine.connect() as connection:
        assert (
            await connection.execute(
                text("SELECT original_bytes FROM snapshot_imports")
            )
        ).scalar_one() == candidate.content
    await engine.dispose()
