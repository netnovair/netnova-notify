from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import TicketPriority, TicketStatus
from app.schemas.common import ORMModel


class TicketMessageOut(ORMModel):
    id: uuid.UUID
    author_type: str
    author_label: str | None
    body: str
    channel: str
    created_at: datetime


class TicketListItem(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_name: str | None = None
    subject: str
    status: str
    priority: str
    created_by_type: str
    preview: str | None = None
    message_count: int
    admin_unread: int
    member_unread: int
    last_message_at: datetime
    is_overdue: bool = False
    created_at: datetime


class TicketDetail(TicketListItem):
    messages: list[TicketMessageOut] = []
    member_display_name: str | None = None
    closed_at: datetime | None = None


class TicketCreate(BaseModel):
    project_id: uuid.UUID
    subject: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=2, max_length=4000)
    priority: TicketPriority = TicketPriority.NORMAL

    @field_validator("subject", "body")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class TicketReply(BaseModel):
    body: str = Field(min_length=2, max_length=4000)

    @field_validator("body")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
