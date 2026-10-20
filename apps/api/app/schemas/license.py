from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel, ensure_timezone


class LicenseOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_name: str | None = None
    code_prefix: str
    status: str
    expires_at: datetime | None
    activated_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    effective_status: str = "pending"


class LicenseCreated(LicenseOut):
    code: str


class LicenseCreate(BaseModel):
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        return ensure_timezone(value)


class LicenseRevoke(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class LicenseCodeOut(BaseModel):
    """The revealed code; never sent in list responses."""

    id: uuid.UUID
    code: str
    code_prefix: str


class LicenseReissue(BaseModel):
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        return ensure_timezone(value)


class LicenseDeliver(BaseModel):
    member_id: uuid.UUID | None = None
