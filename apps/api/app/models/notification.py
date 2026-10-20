from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'queued', 'sending', 'sent', 'failed', 'retry_wait', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint("type IN ('announcement', 'financial', 'system')", name="type_valid"),
        Index("ix_notifications_project_created", "project_id", "created_at"),
        Index("ix_notifications_status", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), default="announcement", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    send_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scheduled_jobs.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    # Providers requested for this notification; each recipient is contacted on
    # the intersection of these and the project's enabled channels.
    channels: Mapped[list] = mapped_column(
        JSONB, default=lambda: ["telegram"], nullable=False, server_default='["telegram"]'
    )

    project: Mapped[Project] = relationship()  # noqa: F821
    deliveries: Mapped[list[DeliveryAttempt]] = relationship(
        back_populates="notification",
        cascade="all, delete-orphan",
        order_by="DeliveryAttempt.attempt_no",
        lazy="selectin",
    )


class DeliveryAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "delivery_attempts"
    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "attempt_no",
            "channel",
            "recipient",
            name="uq_delivery_attempts_notification_attempt_target",
        ),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed', 'unknown')", name="status_valid"
        ),
        Index("ix_delivery_attempts_notification", "notification_id"),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False
    )
    # ``chat_id`` is kept for Telegram-compatible providers (numeric chat ids).
    # ``recipient`` is the provider-agnostic target: a chat id or a phone number.
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    recipient: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    channel: Mapped[str] = mapped_column(
        String(20), default="telegram", nullable=False, server_default="telegram"
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_mock: Mapped[bool] = mapped_column(default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    notification: Mapped[Notification] = relationship(back_populates="deliveries")
