"""Modelos ORM: usuários, workspaces e associação com papéis."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy import (
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkspaceRole(str, enum.Enum):
    """Papel de um usuário dentro de um workspace."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class TimestampMixin:
    """Colunas de auditoria created_at/updated_at."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=_utcnow,
        nullable=False,
    )


class User(Base, TimestampMixin):
    """Conta de usuário autenticável."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Hash da senha (nunca a senha em claro). Opcional para contas externas.
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    memberships: Mapped[List["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Workspace(Base, TimestampMixin):
    """Espaço de trabalho que isola dados entre equipes."""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Slug único e legível para URLs / referência.
    slug: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    memberships: Mapped[List["Membership"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class Membership(Base, TimestampMixin):
    """Associação usuário↔workspace com um papel."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "workspace_id", name="uq_membership_user_workspace"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        SAEnum(WorkspaceRole, name="workspace_role"),
        nullable=False,
        default=WorkspaceRole.MEMBER,
    )

    user: Mapped["User"] = relationship(back_populates="memberships")
    workspace: Mapped["Workspace"] = relationship(back_populates="memberships")
