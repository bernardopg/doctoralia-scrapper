"""Initialize database schema (create tables if not exist)."""

import asyncio
import logging
import sys
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from src.db.base import Base, get_engine, get_sessionmaker
from src.db.models import Membership, User, Workspace, WorkspaceRole

logger = logging.getLogger(__name__)


def _resolve_engine(dsn: Optional[str]) -> AsyncEngine:
    """Return the singleton engine, or a standalone one bound to *dsn*."""
    if dsn is None:
        return get_engine()
    return create_async_engine(dsn, pool_pre_ping=True, future=True)


async def init_db(dsn: Optional[str] = None) -> None:
    """Create all tables defined in metadata if they don't exist.

    Args:
        dsn: Optional database URL. If not provided, uses DATABASE_URL env var
             or default from database_url().
    """
    engine = _resolve_engine(dsn)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized (tables created if not exist)")
    except Exception as exc:
        logger.exception("Failed to initialize database schema: %s", exc)
        raise
    finally:
        if dsn is not None:
            await engine.dispose()


async def drop_db(dsn: Optional[str] = None) -> None:
    """Drop all tables defined in metadata. USE WITH CAUTION."""
    engine = _resolve_engine(dsn)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database schema dropped")
    except Exception as exc:
        logger.exception("Failed to drop database schema: %s", exc)
        raise
    finally:
        if dsn is not None:
            await engine.dispose()


async def seed_db(dsn: Optional[str] = None) -> None:
    """Seed database with initial data (e.g., default workspace)."""
    engine = _resolve_engine(dsn)

    sessionmaker = (
        get_sessionmaker()
        if dsn is None
        else async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    )

    async with sessionmaker() as session:
        try:
            # Check if default workspace already exists
            workspace_result = await session.execute(
                select(Workspace).where(Workspace.slug == "default")
            )
            default_workspace = workspace_result.scalar_one_or_none()

            if default_workspace is None:
                default_workspace = Workspace(
                    name="Default Workspace",
                    slug="default",
                )
                session.add(default_workspace)
                await session.flush()
                logger.info("Created default workspace")

            # Check if any superuser exists
            user_result = await session.execute(
                select(User).where(User.is_superuser.is_(True))
            )
            superuser = user_result.scalar_one_or_none()

            if superuser is None:
                # Create a default superuser (password will need to be set via API)
                superuser = User(
                    email="admin@localhost",
                    display_name="Administrator",
                    is_superuser=True,
                    is_active=True,
                )
                session.add(superuser)
                await session.flush()
                logger.info("Created default superuser (admin@localhost)")

                # Link superuser to default workspace as OWNER
                membership = Membership(
                    user_id=superuser.id,
                    workspace_id=default_workspace.id,
                    role=WorkspaceRole.OWNER,
                )
                session.add(membership)
                logger.info("Linked superuser to default workspace as OWNER")

            await session.commit()
            logger.info("Database seeding completed")
        except Exception as exc:
            await session.rollback()
            logger.exception("Failed to seed database: %s", exc)
            raise
        finally:
            if dsn is not None:
                await engine.dispose()


async def main(argv: list[str] | None = None):
    """CLI entry point for database initialization.

    Args:
        argv: Optional argument list for testing. Defaults to sys.argv[1:].
    """
    import argparse

    parser = argparse.ArgumentParser(description="Database initialization")
    parser.add_argument(
        "command",
        choices=["init", "drop", "seed", "init-and-seed"],
        help="Command to execute",
    )
    parser.add_argument(
        "--dsn",
        help="Database URL (overrides DATABASE_URL env var)",
        default=None,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        if args.command == "init":
            await init_db(args.dsn)
        elif args.command == "drop":
            await drop_db(args.dsn)
        elif args.command == "seed":
            await seed_db(args.dsn)
        elif args.command == "init-and-seed":
            await init_db(args.dsn)
            await seed_db(args.dsn)
    except Exception as exc:
        logger.error("Command '%s' failed: %s", args.command, exc)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
