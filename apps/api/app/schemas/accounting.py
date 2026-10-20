from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class PaymentMethodIn(BaseModel):
    project_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=120)
    card_number: str = Field(min_length=8, max_length=32)
    holder_name: str = Field(default="", max_length=120)
    bank_name: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=2000)
    is_active: bool = True
    order_index: int = Field(default=0, ge=0, le=999)

    @field_validator("title", "holder_name", "bank_name", "note")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("card_number")
    @classmethod
    def _card(cls, value: str) -> str:
        digits = value.replace(" ", "").replace("-", "")
        if not digits.isdigit() or not 8 <= len(digits) <= 32:
            raise ValueError("شماره کارت باید فقط رقم و بین ۸ تا ۳۲ رقم باشد.")
        return digits


class PaymentMethodOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    card_number: str
    holder_name: str
    bank_name: str
    note: str
    is_active: bool
    order_index: int
    created_at: datetime
    updated_at: datetime


class ReceiptFileOut(ORMModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int


class AllocationOut(ORMModel):
    id: uuid.UUID
    payment_id: uuid.UUID
    payment_title: str | None = None
    amount_minor: int


class AllocationIn(BaseModel):
    payment_id: uuid.UUID
    amount_minor: int = Field(gt=0, le=10**15)


class ReceiptOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_name: str | None = None
    member_id: uuid.UUID | None
    member_display_name: str | None = None
    submitted_by_type: str
    amount_minor: int
    currency: str
    tracking_code: str | None
    note: str
    status: str
    review_note: str
    reviewed_at: datetime | None
    channel: str
    files: list[ReceiptFileOut] = []
    allocations: list[AllocationOut] = []
    created_at: datetime


class ReceiptCreate(BaseModel):
    """A receipt entered by the administrator (cash, POS, bank transfer)."""

    amount_minor: int = Field(gt=0, le=10**15)
    currency: Literal["IRR", "IRT", "USD", "EUR"] = "IRT"
    tracking_code: str | None = Field(default=None, max_length=120)
    note: str = Field(default="", max_length=2000)


class ReceiptReview(BaseModel):
    note: str = Field(default="", max_length=2000)
    allocations: list[AllocationIn] | None = None

    @field_validator("note")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class AllocationUpdate(BaseModel):
    allocations: list[AllocationIn]


class CurrencyTotalsOut(BaseModel):
    currency: str
    debt_minor: int
    paid_minor: int
    overdue_minor: int
    credit_minor: int
    balance_minor: int
    invoices_total: int
    invoices_open: int
    pending_receipts: int = 0
    settled: bool = False


class ProjectAccountingOut(BaseModel):
    project_id: uuid.UUID
    project_name: str
    totals: list[CurrencyTotalsOut] = []


class AccountingOverviewOut(BaseModel):
    totals: list[CurrencyTotalsOut] = []
    projects: list[ProjectAccountingOut] = []


class MessageTemplateOut(BaseModel):
    key: str
    title: str
    description: str
    body: str
    default_body: str
    variables: list[str]
    customized: bool
    project_id: uuid.UUID | None = None
    updated_at: datetime | None = None


class MessageTemplateIn(BaseModel):
    body: str = Field(min_length=2, max_length=4000)
    project_id: uuid.UUID | None = None
