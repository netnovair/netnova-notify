"""Light accounting: receipts uploaded by employers, their allocation to invoices.

The existing ``payments`` rows are the invoices. This module adds:

* ``payment_methods`` - card numbers and the pre-written text shown in the bot;
* ``payment_receipts`` - what the employer says they paid (text and/or images);
* ``payment_allocations`` - how one receipt is split across invoices, so partial
  payments and one-payment-covers-two-invoices both work;
* ``message_templates`` - editable texts (reminder, approval, license delivery).

Money never appears in callback data, and attachments follow the ticket model:
bytes live in PostgreSQL because free hosting has an ephemeral disk.
"""

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
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

MAX_RECEIPT_BYTES = 5 * 1024 * 1024
MAX_RECEIPT_FILES = 4


class PaymentMethod(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A card/account the employer can pay into.

    ``project_id`` is nullable: a row without a project is the default shown to
    every employer, a row with a project overrides it for that project only.
    """

    __tablename__ = "payment_methods"
    __table_args__ = (
        CheckConstraint("length(card_number) BETWEEN 8 AND 32", name="card_number_length"),
        Index("ix_payment_methods_project_order", "project_id", "order_index"),
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    card_number: Mapped[str] = mapped_column(String(32), nullable=False)
    holder_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    bank_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PaymentReceipt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One claim of payment, pending admin review."""

    __tablename__ = "payment_receipts"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="receipt_amount_positive"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="receipt_status_valid"
        ),
        CheckConstraint(
            "submitted_by_type IN ('employer', 'admin', 'system')",
            name="receipt_submitter_valid",
        ),
        Index("ix_payment_receipts_project_status", "project_id", "status", "created_at"),
        Index("ix_payment_receipts_member", "member_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_members.id", ondelete="SET NULL"), nullable=True
    )
    submitted_by_type: Mapped[str] = mapped_column(String(20), default="employer", nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IRT", nullable=False)
    tracking_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="telegram", nullable=False)

    project: Mapped[Project] = relationship()  # noqa: F821
    member: Mapped[object | None] = relationship("ProjectMember")
    files: Mapped[list[PaymentReceiptFile]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="PaymentReceiptFile.created_at",
        lazy="selectin",
    )
    allocations: Mapped[list[PaymentAllocation]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="PaymentAllocation.created_at",
        lazy="selectin",
    )


class PaymentReceiptFile(UUIDPrimaryKeyMixin, Base):
    """An image attached to a receipt (proof of transfer)."""

    __tablename__ = "payment_receipt_files"
    __table_args__ = (
        CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 5242880", name="receipt_file_size_valid"
        ),
        Index("ix_payment_receipt_files_receipt", "receipt_id", "created_at"),
    )

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_receipts.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(120), nullable=False)
    content_type: Mapped[str] = mapped_column(String(60), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Deferred: lists need the metadata, only the download endpoint needs bytes.
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    receipt: Mapped[PaymentReceipt] = relationship(back_populates="files")


class PaymentAllocation(UUIDPrimaryKeyMixin, Base):
    """Part of one receipt applied to one invoice."""

    __tablename__ = "payment_allocations"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="allocation_amount_positive"),
        UniqueConstraint("receipt_id", "payment_id", name="uq_payment_allocations_pair"),
        Index("ix_payment_allocations_payment", "payment_id"),
    )

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_receipts.id", ondelete="CASCADE"), nullable=False
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    receipt: Mapped[PaymentReceipt] = relationship(back_populates="allocations")
    payment: Mapped[Payment] = relationship()  # noqa: F821


class MessageTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Editable Telegram text, either global (``project_id`` null) or per project."""

    __tablename__ = "message_templates"
    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_message_templates_project_key"),
        Index(
            "uq_message_templates_global_key",
            "key",
            unique=True,
            postgresql_where=text("project_id IS NULL"),
        ),
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
