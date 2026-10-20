"""Public service catalog and pre-sales orders ("ثبت سفارش").

The catalog is a two-level tree (main service -> sub service) and every sub
service owns an ordered list of questions. A visitor without a license walks
that tree inside Telegram; the answers are stored as a JSON snapshot so later
catalog edits never rewrite the history of a submitted order.

Deleting a category or an item is refused while requests reference it; the
panel offers archiving (``is_active = false``) instead, which keeps the bot menu
clean without losing data.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
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

QUESTION_TYPES = ("text", "long_text", "number", "choice", "phone")
REQUEST_STATUSES = ("new", "contacted", "quoted", "won", "lost", "cancelled")


def _question_types_sql() -> str:
    values = ", ".join(f"'{item}'" for item in QUESTION_TYPES)
    return f"field_type IN ({values})"


def _request_statuses_sql() -> str:
    values = ", ".join(f"'{item}'" for item in REQUEST_STATUSES)
    return f"status IN ({values})"


class ServiceCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A main service such as «خدمات گرافیکی»."""

    __tablename__ = "service_categories"
    __table_args__ = (
        UniqueConstraint("key", name="uq_service_categories_key"),
        Index("ix_service_categories_active_order", "is_active", "order_index"),
    )

    key: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    emoji: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    #: Show a short "نمونه کارها" block after the item list.
    show_portfolio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    portfolio_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    #: Optional public image URL sent by the bot as a photo (never uploaded by us).
    portfolio_url: Mapped[str] = mapped_column(
        String(500), default="", server_default="", nullable=False
    )

    items: Mapped[list[ServiceItem]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="ServiceItem.order_index",
    )


class ServiceItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A sub service such as «طراحی لوگو»."""

    __tablename__ = "service_items"
    __table_args__ = (
        UniqueConstraint("category_id", "key", name="uq_service_items_category_key"),
        Index("ix_service_items_category_order", "category_id", "order_index"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_categories.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_portfolio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    portfolio_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    portfolio_url: Mapped[str] = mapped_column(
        String(500), default="", server_default="", nullable=False
    )

    category: Mapped[ServiceCategory] = relationship(back_populates="items")
    questions: Mapped[list[ServiceQuestion]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ServiceQuestion.order_index",
    )


class ServiceQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One question asked while the visitor configures a sub service."""

    __tablename__ = "service_questions"
    __table_args__ = (
        UniqueConstraint("item_id", "key", name="uq_service_questions_item_key"),
        CheckConstraint(_question_types_sql(), name="field_type_valid"),
        Index("ix_service_questions_item_order", "item_id", "order_index"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_items.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    help_text: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), default="text", nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    #: Allowed answers for ``choice`` questions (also used for quick-reply buttons).
    options: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    min_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    item: Mapped[ServiceItem] = relationship(back_populates="questions")


class ServiceRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A submitted pre-sales order.

    Titles are snapshotted so an order stays readable after the catalog changes.
    The user's contact details are copied here as well: the admin must be able to
    call the lead even if the Telegram account is deleted later.
    """

    __tablename__ = "service_requests"
    __table_args__ = (
        CheckConstraint(_request_statuses_sql(), name="status_valid"),
        Index("ix_service_requests_status_created", "status", "created_at"),
        Index("ix_service_requests_user", "telegram_user_id"),
    )

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_categories.id", ondelete="SET NULL"), nullable=True
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_items.id", ondelete="SET NULL"), nullable=True
    )
    telegram_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telegram_users.id", ondelete="SET NULL"), nullable=True
    )
    category_title: Mapped[str] = mapped_column(String(120), nullable=False)
    item_title: Mapped[str] = mapped_column(String(120), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    #: ``[{"key": ..., "label": ..., "value": ...}]`` - stable, human readable.
    answers: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False)
    admin_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="telegram", nullable=False)
    telegram_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    category: Mapped[ServiceCategory | None] = relationship()
    item: Mapped[ServiceItem | None] = relationship()


class OrderSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """In-progress order conversation for one Telegram user.

    Kept separate from ``telegram_conversations`` because an order is not tied to
    a project and must work for visitors without any license. The payload holds
    only short-lived UI state (chosen indices and collected answers); the final
    values are written to ``service_requests``.
    """

    __tablename__ = "order_sessions"
    __table_args__ = (
        UniqueConstraint("telegram_user_id", name="uq_order_sessions_user"),
        Index("ix_order_sessions_expires", "expires_at"),
    )

    telegram_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telegram_users.id", ondelete="CASCADE"), nullable=False
    )
    step: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
