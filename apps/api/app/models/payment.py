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
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="amount_positive"),
        CheckConstraint("status IN ('unpaid', 'paid', 'cancelled')", name="status_valid"),
        CheckConstraint("currency IN ('IRR', 'IRT', 'USD', 'EUR')", name="currency_valid"),
        Index("ix_payments_project_due", "project_id", "due_at"),
        Index("ix_payments_status_due", "status", "due_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IRR", nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="unpaid", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scheduled_jobs.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped[Project] = relationship()  # noqa: F821
