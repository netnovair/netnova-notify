from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class License(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "licenses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'revoked', 'expired')", name="status_valid"
        ),
        # At most one live (pending/active) license per project.
        Index(
            "uq_licenses_live_project",
            "project_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'active')"),
        ),
        Index("ix_licenses_project_created", "project_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    code_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="licenses")  # noqa: F821
