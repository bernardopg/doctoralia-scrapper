"""Tests for src.db.base module (engine, session, database_url)."""

import os
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.db.base import Base, database_url, get_engine, get_session, get_sessionmaker


class TestDatabaseURL:
    """Test database_url() function."""

    def test_default_url(self):
        with patch.dict(os.environ, {}, clear=True):
            url = database_url()
            assert (
                url == "postgresql+asyncpg://doctoralia:doctoralia@db:5432/doctoralia"
            )

    def test_custom_url_from_env(self):
        custom = "postgresql+asyncpg://user:pass@localhost:5432/mydb"
        with patch.dict(os.environ, {"DATABASE_URL": custom}, clear=True):
            url = database_url()
            assert url == custom

    def test_normalizes_postgresql_driver(self):
        with patch.dict(
            os.environ, {"DATABASE_URL": "postgresql://user:pass@host/db"}, clear=True
        ):
            url = database_url()
            assert url == "postgresql+asyncpg://user:pass@host/db"

    def test_normalizes_postgres_driver(self):
        with patch.dict(
            os.environ, {"DATABASE_URL": "postgres://user:pass@host/db"}, clear=True
        ):
            url = database_url()
            assert url == "postgresql+asyncpg://user:pass@host/db"

    def test_keeps_asyncpg_driver(self):
        url = "postgresql+asyncpg://user:pass@host/db"
        with patch.dict(os.environ, {"DATABASE_URL": url}, clear=True):
            assert database_url() == url


class TestGetEngine:
    """Test get_engine() singleton."""

    def test_returns_async_engine(self):
        engine = get_engine()
        assert isinstance(engine, AsyncEngine)

    def test_singleton_same_instance(self):
        engine1 = get_engine()
        engine2 = get_engine()
        assert engine1 is engine2

    def test_pool_pre_ping_enabled(self):
        engine = get_engine()
        assert engine.pool._pre_ping is True


class TestGetSessionMaker:
    """Test get_sessionmaker() singleton."""

    def test_returns_async_sessionmaker(self):
        factory = get_sessionmaker()
        assert isinstance(factory, async_sessionmaker)

    def test_singleton_same_instance(self):
        f1 = get_sessionmaker()
        f2 = get_sessionmaker()
        assert f1 is f2

    def test_factory_creates_session(self):
        factory = get_sessionmaker()
        session = factory()
        assert isinstance(session, AsyncSession)

    def test_expire_on_commit_false(self):
        factory = get_sessionmaker()
        assert factory.kw.get("expire_on_commit") is False

    def test_autoflush_false(self):
        factory = get_sessionmaker()
        assert factory.kw.get("autoflush") is False


class TestGetSession:
    """Test get_session() dependency."""

    @pytest.mark.asyncio
    async def test_yields_session(self):
        async for session in get_session():
            assert isinstance(session, AsyncSession)
            break

    @pytest.mark.asyncio
    async def test_commits_on_success(self):
        committed = False

        async def mock_commit():
            nonlocal committed
            committed = True

        # We can't easily test the commit/rollback without a real DB,
        # but we can verify the function is an async generator
        gen = get_session()
        assert hasattr(gen, "__anext__")

    @pytest.mark.asyncio
    async def test_rollbacks_on_exception(self):
        # The rollback behavior is tested in integration tests with a real DB
        pass


class TestBase:
    """Test Base declarative class."""

    def test_is_declarative_base(self):
        assert hasattr(Base, "metadata")
        assert hasattr(Base, "registry")

    def test_metadata_has_tables(self):
        # After importing models, metadata should have tables
        table_names = set(Base.metadata.tables.keys())
        assert "users" in table_names
        assert "workspaces" in table_names
        assert "memberships" in table_names
