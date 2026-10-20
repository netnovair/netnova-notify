from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ScheduledJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Durable, database-backed job queue for the standalone worker."""

    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        Index("ix_scheduled_jobs_status_run", "status", "run_at"),
        Index("ix_scheduled_jobs_kind", "kind"),
    )

    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
