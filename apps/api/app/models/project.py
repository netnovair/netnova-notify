from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (CheckConstraint("status IN ('active', 'inactive')", name="status_valid"),)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    client_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_demo: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    telegram_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Archived projects stay readable for history but are hidden from the active
    # list, cannot send notifications and are rejected by the employer bot.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    features: Mapped[list[ProjectFeature]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
    members: Mapped[list[ProjectMember]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
    licenses: Mapped[list[License]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
    channels: Mapped[list[ProjectChannel]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )


class ProjectFeature(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "project_features"
    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_project_features_project_key"),
        Index("ix_project_features_project_id", "project_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    # Feature-specific configuration (validated by the feature plugin itself).
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default="{}")

    project: Mapped[Project] = relationship(back_populates="features")


class ProjectChannel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Which notification providers a project is allowed to use.

    Credentials stay in the environment (one central account per provider); this
    table only records the per-project enablement and a small JSON ``settings``
    bag for provider-specific options that are safe to show to admins.
    """

    __tablename__ = "project_channels"
    __table_args__ = (
        UniqueConstraint("project_id", "channel", name="uq_project_channels_project_channel"),
        Index("ix_project_channels_project_id", "project_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default="{}")

    project: Mapped[Project] = relationship(back_populates="channels")
