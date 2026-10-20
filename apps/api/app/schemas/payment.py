from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import Currency
from app.schemas.common import ORMModel, ensure_timezone


class PaymentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    amount_minor: int = Field(gt=0, le=10**15)
    currency: Currency = Currency.IRT
    due_at: datetime
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("due_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        result = ensure_timezone(value)
        assert result is not None
        return result


class PaymentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    amount_minor: int | None = Field(default=None, gt=0, le=10**15)
    currency: Currency | None = None
    due_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    status: Literal["cancelled"] | None = None

    @field_validator("title")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("due_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        return ensure_timezone(value)


class PaymentOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_name: str | None = None
    title: str
    amount_minor: int
    currency: str
    due_at: datetime
    status: str
    notes: str | None
    paid_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_overdue: bool = False
    next_reminder_at: datetime | None = None
