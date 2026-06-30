"""Tests for src.db.init_db module."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.db.base import Base
from src.db.init_db import drop_db, init_db, main, seed_db
from src.db.models import Membership, User, Workspace, WorkspaceRole


class TestInitDB:
    """Test init_db function."""

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self):
        # Use file-based SQLite so multiple engines can share the DB
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            dsn = f"sqlite+aiosqlite:///{db_path}"
            engine = create_async_engine(dsn, future=True)

            await init_db(dsn=dsn)

            # Verify tables were created
            def check_tables(sync_conn):
                from sqlalchemy import inspect

                insp = inspect(sync_conn)
                return set(insp.get_table_names())

            async with engine.begin() as conn:
                tables = await conn.run_sync(check_tables)
            assert "users" in tables
            assert "workspaces" in tables
            assert "memberships" in tables

            await engine.dispose()
        finally:
            os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_init_db_idempotent(self):
        """Calling init_db twice should not fail."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            dsn = f"sqlite+aiosqlite:///{db_path}"
            engine = create_async_engine(dsn, future=True)

            await init_db(dsn=dsn)
            await init_db(dsn=dsn)

            # Should not raise
            await engine.dispose()
        finally:
            os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_init_db_uses_default_url(self):
        """Test that init_db uses default DATABASE_URL when none provided."""
        with patch("src.db.init_db.get_engine") as mock_get_engine:
            mock_engine = MagicMock()
            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__.return_value = mock_conn
            mock_get_engine.return_value = mock_engine

            await init_db()

            mock_get_engine.assert_called_once()
            mock_engine.begin.assert_called_once()
            mock_conn.run_sync.assert_called_once()


class TestDropDB:
    """Test drop_db function."""

    @pytest.mark.asyncio
    async def test_drop_db_drops_tables(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            dsn = f"sqlite+aiosqlite:///{db_path}"
            engine = create_async_engine(dsn, future=True)

            # First create tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Verify tables exist
            def check_tables(sync_conn):
                from sqlalchemy import inspect

                insp = inspect(sync_conn)
                return set(insp.get_table_names())

            async with engine.begin() as conn:
                tables_before = await conn.run_sync(check_tables)
            assert "users" in tables_before

            # Drop tables
            await drop_db(dsn=dsn)

            # Verify tables are gone
            async with engine.begin() as conn:
                tables_after = await conn.run_sync(check_tables)
            assert "users" not in tables_after

            await engine.dispose()
        finally:
            os.unlink(db_path)


class TestSeedDB:
    """Test seed_db function."""

    def _create_test_db(self):
        """Create a temporary SQLite database with tables."""
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = f.name
        f.close()
        dsn = f"sqlite+aiosqlite:///{db_path}"
        engine = create_async_engine(dsn, future=True)
        return dsn, engine, db_path

    async def _cleanup_db(self, engine, db_path):
        await engine.dispose()
        os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_seed_db_creates_default_workspace(self):
        dsn, engine, db_path = self._create_test_db()
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            await seed_db(dsn=dsn)

            # Verify default workspace was created
            SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

            async with SessionLocal() as session:
                result = await session.execute(
                    select(Workspace).where(Workspace.slug == "default")
                )
                ws = result.scalar_one_or_none()
                assert ws is not None
                assert ws.name == "Default Workspace"
                assert ws.slug == "default"
        finally:
            await self._cleanup_db(engine, db_path)

    @pytest.mark.asyncio
    async def test_seed_db_creates_superuser(self):
        dsn, engine, db_path = self._create_test_db()
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            await seed_db(dsn=dsn)

            # Verify superuser was created
            SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

            async with SessionLocal() as session:
                result = await session.execute(
                    select(User).where(User.is_superuser.is_(True))
                )
                user = result.scalar_one_or_none()
                assert user is not None
                assert user.email == "admin@localhost"
                assert user.is_superuser is True
                assert user.is_active is True
        finally:
            await self._cleanup_db(engine, db_path)

    @pytest.mark.asyncio
    async def test_seed_db_links_user_to_workspace(self):
        dsn, engine, db_path = self._create_test_db()
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            await seed_db(dsn=dsn)

            # Verify membership was created linking user to workspace
            SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

            async with SessionLocal() as session:
                result = await session.execute(
                    select(Workspace).where(Workspace.slug == "default")
                )
                ws = result.scalar_one_or_none()

                result = await session.execute(
                    select(User).where(User.is_superuser.is_(True))
                )
                user = result.scalar_one_or_none()

                result = await session.execute(
                    select(Membership).where(
                        Membership.user_id == user.id,
                        Membership.workspace_id == ws.id,
                    )
                )
                membership = result.scalar_one_or_none()
                assert membership is not None
                assert membership.role == WorkspaceRole.OWNER
        finally:
            await self._cleanup_db(engine, db_path)

    @pytest.mark.asyncio
    async def test_seed_db_idempotent(self):
        """Running seed_db twice should not create duplicates."""
        dsn, engine, db_path = self._create_test_db()
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            await seed_db(dsn=dsn)
            await seed_db(dsn=dsn)

            # Verify only one workspace, one user, one membership
            SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

            async with SessionLocal() as session:
                ws_count = await session.execute(select(func.count(Workspace.id)))
                user_count = await session.execute(select(func.count(User.id)))
                membership_count = await session.execute(
                    select(func.count(Membership.id))
                )

                assert ws_count.scalar() == 1
                assert user_count.scalar() == 1
                assert membership_count.scalar() == 1
        finally:
            await self._cleanup_db(engine, db_path)


class TestMainCLI:
    """Test CLI main function."""

    @pytest.mark.asyncio
    async def test_main_init_command(self):
        with patch("src.db.init_db.init_db") as mock_init:
            mock_init.return_value = None
            await main(["init"])

        mock_init.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_main_drop_command(self):
        with patch("src.db.init_db.drop_db") as mock_drop:
            mock_drop.return_value = None
            await main(["drop"])

        mock_drop.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_main_seed_command(self):
        with patch("src.db.init_db.seed_db") as mock_seed:
            mock_seed.return_value = None
            await main(["seed"])

        mock_seed.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_main_init_and_seed_command(self):
        with (
            patch("src.db.init_db.init_db") as mock_init,
            patch("src.db.init_db.seed_db") as mock_seed,
        ):
            mock_init.return_value = None
            mock_seed.return_value = None
            await main(["init-and-seed"])

        mock_init.assert_called_once_with(None)
        mock_seed.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_main_invalid_command(self):
        with pytest.raises(SystemExit):
            await main(["invalid-command"])

    @pytest.mark.asyncio
    async def test_main_passes_dsn(self):
        with patch("src.db.init_db.init_db") as mock_init:
            mock_init.return_value = None
            await main(["init", "--dsn", "sqlite+aiosqlite:///:memory:"])

        mock_init.assert_called_once_with("sqlite+aiosqlite:///:memory:")

    @pytest.mark.asyncio
    async def test_main_help(self):
        # Test that argparse handles help correctly
        with pytest.raises(SystemExit):
            await main(["--help"])
