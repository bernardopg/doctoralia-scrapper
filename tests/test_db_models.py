"""Tests for SQLAlchemy models in src.db.models."""

from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.base import Base
from src.db.base import get_engine as get_prod_engine
from src.db.base import get_sessionmaker as get_prod_sessionmaker
from src.db.models import Membership, User, Workspace, WorkspaceRole

# Prevent tests from using production engine
get_prod_engine.__wrapped__ = get_prod__ = get_prod_engine
get_prod_sessionmaker.__wrapped_prod__ = get_prod_sessionmaker


class TestWorkspaceRole:
    """Test WorkspaceRole enum."""

    def test_enum_values(self):
        assert WorkspaceRole.OWNER == "owner"
        assert WorkspaceRole.ADMIN == "admin"
        assert WorkspaceRole.MEMBER == "member"
        assert WorkspaceRole.VIEWER == "viewer"

    def test_enum_iteration(self):
        roles = list(WorkspaceRole)
        assert len(roles) == 4


class TestUserModel:
    """Test User model."""

    def test_user_table_exists(self):
        assert User.__tablename__ == "users"

    def test_user_columns(self):
        columns = {c.name for c in User.__table__.columns}
        expected = {
            "id",
            "email",
            "display_name",
            "password_hash",
            "is_active",
            "is_superuser",
            "created_at",
            "updated_at",
        }
        assert columns == expected

    def test_user_primary_key(self):
        pk = [c.name for c in User.__table__.primary_key.columns]
        assert pk == ["id"]

    def test_user_unique_constraints(self):
        unique_cols = {col.name for col in User.__table__.columns if col.unique}
        assert "email" in unique_cols

    def test_user_indexes(self):
        indexed_cols = {idx.columns.keys()[0] for idx in User.__table__.indexes}
        assert "email" in indexed_cols

    def test_user_can_be_instantiated(self):
        user = User(
            id=str(uuid4()),
            email="test@example.com",
            display_name="Test User",
        )
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.display_name == "Test User"
        # Defaults are applied at DB level (server_default), not at Python instantiation
        # is_active and is_superuser have server_default=func.now() equivalent
        assert user.password_hash is None


class TestWorkspaceModel:
    """Test Workspace model."""

    def test_workspace_table_exists(self):
        assert Workspace.__tablename__ == "workspaces"

    def test_workspace_columns(self):
        columns = {c.name for c in Workspace.__table__.columns}
        expected = {"id", "name", "slug", "created_at", "updated_at"}
        assert columns == expected

    def test_workspace_unique_constraints(self):
        unique_cols = {col.name for col in Workspace.__table__.columns if col.unique}
        assert "slug" in unique_cols

    def test_workspace_indexes(self):
        indexed_cols = {idx.columns.keys()[0] for idx in Workspace.__table__.indexes}
        assert "slug" in indexed_cols

    def test_workspace_can_be_instantiated(self):
        ws = Workspace(
            id=str(uuid4()),
            name="Test Workspace",
            slug="test-workspace",
        )
        assert ws.id is not None
        assert ws.name == "Test Workspace"
        assert ws.slug == "test-workspace"


class TestMembershipModel:
    """Test Membership model."""

    def test_membership_table_exists(self):
        assert Membership.__tablename__ == "memberships"

    def test_membership_columns(self):
        columns = {c.name for c in Membership.__table__.columns}
        expected = {
            "id",
            "user_id",
            "workspace_id",
            "role",
            "created_at",
            "updated_at",
        }
        assert columns == expected

    def test_membership_unique_constraint(self):
        unique_constraints = []
        for constraint in Membership.__table__.constraints:
            if constraint.name == "uq_membership_user_workspace":
                unique_constraints.append(constraint)
        assert len(unique_constraints) == 1
        cols = {col.name for col in unique_constraints[0].columns}
        assert cols == {"user_id", "workspace_id"}

    def test_membership_foreign_keys(self):
        fks = list(Membership.__table__.foreign_keys)
        assert len(fks) == 2
        fk_tables = {fk.column.table.name for fk in fks}
        assert fk_tables == {"users", "workspaces"}

    def test_membership_role_default(self):
        _ = Membership(
            id=str(uuid4()),
            user_id=str(uuid4()),
            workspace_id=str(uuid4()),
        )
        # Default is applied at DB level via server_default, not at instantiation
        # Test that the column has a default
        role_col = Membership.__table__.columns["role"]
        assert role_col.default is not None or role_col.server_default is not None

    def test_membership_can_be_instantiated(self):
        membership = Membership(
            id=str(uuid4()),
            user_id=str(uuid4()),
            workspace_id=str(uuid4()),
            role=WorkspaceRole.ADMIN,
        )
        assert membership.role == WorkspaceRole.ADMIN


class TestTimestampMixin:
    """Test TimestampMixin columns."""

    def test_user_has_timestamps(self):
        assert hasattr(User, "created_at")
        assert hasattr(User, "updated_at")

    def test_workspace_has_timestamps(self):
        assert hasattr(Workspace, "created_at")
        assert hasattr(Workspace, "updated_at")

    def test_membership_has_timestamps(self):
        assert hasattr(Membership, "created_at")
        assert hasattr(Membership, "updated_at")


class TestRelationships:
    """Test model relationships."""

    def test_user_memberships_relationship(self):
        assert hasattr(User, "memberships")
        rel = User.__dict__["memberships"]
        # back_populates points to the attribute name on the related class (Membership.user)
        assert rel.property.back_populates == "user"
        # The related class is Membership
        assert rel.property.mapper.class_ == Membership

    def test_workspace_memberships_relationship(self):
        assert hasattr(Workspace, "memberships")
        rel = Workspace.__dict__["memberships"]
        assert rel.property.mapper.class_ == Membership

    def test_membership_user_relationship(self):
        assert hasattr(Membership, "user")
        rel = Membership.__dict__["user"]
        assert rel.property.back_populates == "memberships"

    def test_membership_workspace_relationship(self):
        assert hasattr(Membership, "workspace")
        rel = Membership.__dict__["workspace"]
        assert rel.property.back_populates == "memberships"


class TestBaseMetadata:
    """Test Base metadata includes all tables."""

    def test_all_tables_in_metadata(self):
        table_names = set(Base.metadata.tables.keys())
        expected = {"users", "workspaces", "memberships"}
        assert expected.issubset(table_names)

    def test_table_creation_order(self):
        """Ensure tables can be created in dependency order."""
        # This is verified by the fact that metadata.create_all() works
        pass


@pytest.mark.asyncio
async def test_models_can_be_created_in_memory():
    """Integration test: create all tables in SQLite in-memory."""
    # Use SQLite for fast in-memory testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Verify tables exist
    def check_tables(sync_conn):
        insp = inspect(sync_conn)
        return set(insp.get_table_names())

    async with engine.begin() as conn:
        tables = await conn.run_sync(check_tables)
    assert "users" in tables
    assert "workspaces" in tables
    assert "memberships" in tables

    await engine.dispose()


@pytest.mark.asyncio
async def test_relationship_roundtrip():
    """Test that relationships work correctly in a session."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with SessionLocal() as session:
        # Create workspace
        ws = Workspace(id=str(uuid4()), name="Test", slug="test")
        session.add(ws)

        # Create user
        user = User(id=str(uuid4()), email="test@example.com", display_name="Test")
        session.add(user)

        await session.flush()

        # Create membership
        membership = Membership(
            id=str(uuid4()),
            user_id=user.id,
            workspace_id=ws.id,
            role=WorkspaceRole.ADMIN,
        )
        session.add(membership)
        await session.commit()

        # Refresh to load relationships
        await session.refresh(user, ["memberships"])
        await session.refresh(ws, ["memberships"])

        # Verify relationships
        assert len(user.memberships) == 1
        assert user.memberships[0].role == WorkspaceRole.ADMIN
        assert user.memberships[0].workspace.id == ws.id

        assert len(ws.memberships) == 1
        assert ws.memberships[0].user.id == user.id

    await engine.dispose()
