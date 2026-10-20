from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('admin', 'telegram_user', 'system')", name="actor_type_valid"
        ),
        Index("ix_audit_logs_project_created", "project_id", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
