from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MemberChannelIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """How to reach one project member on a non-Telegram provider.

    Telegram identity stays in ``telegram_users`` (the bot owns it). This table
    stores the extra destinations an admin configures manually, so notification
    fan-out can reach the same person on Bale, Eitaa or SMS.
    """

    __tablename__ = "member_channel_identities"
    __table_args__ = (
        UniqueConstraint("project_member_id", "channel", name="uq_member_channel_member_channel"),
        UniqueConstraint("channel", "external_id", name="uq_member_channel_external"),
        Index("ix_member_channel_project", "project_id", "channel"),
        CheckConstraint("length(external_id) >= 3", name="external_id_length"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    project_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_members.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    member: Mapped[ProjectMember] = relationship(  # noqa: F821
        back_populates="channel_identities"
    )


class Ticket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Two-way support thread between the agency and one project employer."""

    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'pending_admin', 'pending_employer', 'closed')",
            name="status_valid",
        ),
        CheckConstraint("priority IN ('low', 'normal', 'high')", name="priority_valid"),
        Index("ix_tickets_project_status", "project_id", "status"),
        Index("ix_tickets_last_message", "last_message_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_members.id", ondelete="SET NULL"), nullable=True
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="open", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="normal", nullable=False)
    created_by_type: Mapped[str] = mapped_column(String(20), default="employer", nullable=False)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    admin_unread: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    member_unread: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship()  # noqa: F821
    messages: Mapped[list[TicketMessage]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketMessage.created_at",
        lazy="selectin",
    )


class TicketMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ticket_messages"
    __table_args__ = (Index("ix_ticket_messages_ticket_created", "ticket_id", "created_at"),)

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_type: Mapped[str] = mapped_column(String(20), nullable=False)
    author_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    author_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_members.id", ondelete="SET NULL"), nullable=True
    )
    author_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="web", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ticket: Mapped[Ticket] = relationship(back_populates="messages")


class TelegramConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Pending multi-step Telegram input (ticket subject/body/reply).

    Callback payloads never carry database ids; the state row keeps the target on
    the server instead. A stale conversation expires automatically.
    """

    __tablename__ = "telegram_conversations"
    __table_args__ = (
        UniqueConstraint("telegram_user_id", "project_id", name="uq_conversation_user_project"),
        Index("ix_conversations_expires", "expires_at"),
    )

    telegram_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telegram_users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    step: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
