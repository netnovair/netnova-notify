from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class MemberOut(ORMModel):
    id: uuid.UUID
    telegram_id: int | None
    display_name: str
    username: str | None
    role: str
    status: str
    activated_at: datetime | None
    created_at: datetime
    #: Non-Telegram destinations (bale/eitaa/smsir) for this member.
    channel_identities: list[MemberChannelIdentityOut] = []


class MemberChannelIdentityOut(ORMModel):
    channel: str
    external_id: str
    label: str | None


class MemberChannelUpdate(BaseModel):
    external_id: str = Field(min_length=3, max_length=120)
    label: str | None = Field(default=None, max_length=120)


class ActivationRequest(BaseModel):
    code: str = Field(min_length=8, max_length=64)
    telegram_id: int = Field(gt=0)
    username: str | None = Field(default=None, max_length=120)
    first_name: str | None = Field(default=None, max_length=160)
    last_name: str | None = Field(default=None, max_length=160)


class ActivationResult(BaseModel):
    status: str
    membership_status: str
    project_id: uuid.UUID
    project_name: str
    message: str
    already_active: bool = False
