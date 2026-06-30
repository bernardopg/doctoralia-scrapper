"""Engine, sessão e base declarativa do SQLAlchemy (async)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa de todos os modelos ORM."""


def database_url() -> str:
    """URL de conexão assíncrona do PostgreSQL.

    Lê `DATABASE_URL` do ambiente e normaliza o driver para `asyncpg`. Aceita
    tanto `postgresql://` quanto `postgresql+asyncpg://`. Default aponta para o
    serviço `db` da stack Docker.
    """
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://doctoralia:doctoralia@db:5432/doctoralia",
    )
    # Normaliza drivers síncronos para o async equivalente.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Engine async singleton (pool com pre-ping)."""
    return create_async_engine(
        database_url(),
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Fábrica de sessões async singleton."""
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependency do FastAPI: cede uma sessão e garante o fechamento.

    Faz commit no sucesso e rollback em exceção, dentro do escopo da request.
    """
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
