from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TelegramUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "telegram_users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    #: Remembered so a returning visitor is not asked for the basics again.
    contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    #: When the persistent reply keyboard was last sent (avoids re-sending it).
    menu_keyboard_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    memberships: Mapped[list[ProjectMember]] = relationship(back_populates="telegram_user")


class ProjectMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "telegram_user_id", name="uq_project_members_project_user"),
        CheckConstraint("status IN ('pending_approval', 'active', 'revoked')", name="status_valid"),
        CheckConstraint("role IN ('owner', 'member')", name="role_valid"),
        Index("ix_project_members_project_status", "project_id", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    telegram_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telegram_users.id", ondelete="CASCADE"), nullable=False
    )
    license_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("licenses.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(20), default="owner", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending_approval", nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="members")  # noqa: F821
    telegram_user: Mapped[TelegramUser] = relationship(back_populates="memberships")
    license: Mapped[License | None] = relationship()  # noqa: F821
    channel_identities: Mapped[list[MemberChannelIdentity]] = relationship(  # noqa: F821
        cascade="all, delete-orphan", order_by="MemberChannelIdentity.channel"
    )


class TelegramUpdate(UUIDPrimaryKeyMixin, Base):
    """Idempotency record so a retried webhook delivery is processed only once."""

    __tablename__ = "telegram_updates"

    update_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed: Mapped[bool] = mapped_column(default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
