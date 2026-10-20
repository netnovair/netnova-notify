from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import NotificationType
from app.schemas.common import ORMModel, ensure_timezone


class NotificationCreate(BaseModel):
    type: NotificationType = NotificationType.ANNOUNCEMENT
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=2, max_length=3500)
    scheduled_at: datetime | None = None
    #: Providers requested for this message; each must be enabled for the project.
    channels: list[str] = ["telegram"]

    @field_validator("title", "body")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("scheduled_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        return ensure_timezone(value)


class DeliveryOut(ORMModel):
    id: uuid.UUID
    channel: str
    recipient: str
    chat_id: int | None
    status: str
    attempt_no: int
    telegram_message_id: int | None
    error: str | None
    is_mock: bool
    started_at: datetime
    finished_at: datetime | None


class NotificationOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    type: str
    title: str
    body: str
    status: str
    scheduled_at: datetime | None
    queued_at: datetime | None
    sent_at: datetime | None
    cancelled_at: datetime | None
    attempt_count: int
    last_error: str | None
    telegram_message_id: int | None
    channels: list[str] = []
    created_at: datetime
    updated_at: datetime
    deliveries: list[DeliveryOut] = []


class NotificationListItem(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_name: str | None = None
    type: str
    title: str
    status: str
    scheduled_at: datetime | None
    sent_at: datetime | None
    attempt_count: int
    last_error: str | None
    is_mock: bool
    created_at: datetime
