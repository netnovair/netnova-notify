from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.catalog import QUESTION_TYPES, REQUEST_STATUSES
from app.schemas.common import ORMModel

QuestionType = Literal["text", "long_text", "number", "choice", "phone"]
RequestStatus = Literal["new", "contacted", "quoted", "won", "lost", "cancelled"]

assert set(QUESTION_TYPES) == {
    "text",
    "long_text",
    "number",
    "choice",
    "phone",
}, "QuestionType must stay in sync with the database constraint."
assert set(REQUEST_STATUSES) == {
    "new",
    "contacted",
    "quoted",
    "won",
    "lost",
    "cancelled",
}, "RequestStatus must stay in sync with the database constraint."


class QuestionIn(BaseModel):
    key: str | None = Field(default=None, max_length=60)
    label: str = Field(min_length=2, max_length=300)
    help_text: str = Field(default="", max_length=500)
    field_type: QuestionType = "text"
    required: bool = True
    options: list[str] = Field(default_factory=list)
    min_value: int | None = Field(default=None, ge=0, le=1_000_000)
    max_value: int | None = Field(default=None, ge=0, le=1_000_000)
    order_index: int = Field(default=0, ge=0, le=999)
    is_active: bool = True

    @field_validator("options")
    @classmethod
    def _clean_options(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            text = item.strip()
            if text and text not in cleaned:
                cleaned.append(text[:120])
        return cleaned[:12]

    @model_validator(mode="after")
    def _validate(self) -> QuestionIn:
        if self.field_type == "choice" and len(self.options) < 2:
            raise ValueError("سوال انتخابی باید حداقل دو گزینه داشته باشد.")
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError("حداقل مقدار نمی تواند از حداکثر بیشتر باشد.")
        return self


class QuestionOut(ORMModel):
    id: uuid.UUID
    key: str
    label: str
    help_text: str
    field_type: str
    required: bool
    options: list[str]
    min_value: int | None
    max_value: int | None
    order_index: int
    is_active: bool


class ItemIn(BaseModel):
    key: str | None = Field(default=None, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=2, max_length=120)
    description: str = ""
    order_index: int = Field(default=0, ge=0, le=999)
    is_active: bool = True
    show_portfolio: bool = False
    portfolio_text: str = ""
    portfolio_url: str = Field(default="", max_length=500)
    #: ``None`` leaves the questions untouched on update. An empty list clears them.
    questions: list[QuestionIn] | None = None

    @field_validator("portfolio_url")
    @classmethod
    def _validate_portfolio_url(cls, value: str) -> str:
        url = (value or "").strip()
        if url and not url.startswith("https://"):
            raise ValueError("آدرس تصویر باید با https:// شروع شود.")
        return url


class ItemOut(ORMModel):
    id: uuid.UUID
    key: str
    title: str
    description: str
    order_index: int
    is_active: bool
    show_portfolio: bool
    portfolio_text: str
    portfolio_url: str
    questions: list[QuestionOut]


class CategoryIn(BaseModel):
    key: str | None = Field(default=None, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=2, max_length=120)
    description: str = ""
    emoji: str = Field(default="", max_length=16)
    order_index: int = Field(default=0, ge=0, le=999)
    is_active: bool = True
    show_portfolio: bool = False
    portfolio_text: str = ""
    portfolio_url: str = Field(default="", max_length=500)

    @field_validator("portfolio_url")
    @classmethod
    def _validate_portfolio_url(cls, value: str) -> str:
        url = (value or "").strip()
        if url and not url.startswith("https://"):
            raise ValueError("آدرس تصویر باید با https:// شروع شود.")
        return url


class CategoryOut(ORMModel):
    id: uuid.UUID
    key: str
    title: str
    description: str
    emoji: str
    order_index: int
    is_active: bool
    show_portfolio: bool
    portfolio_text: str
    portfolio_url: str
    items: list[ItemOut]


class CatalogOut(BaseModel):
    categories: list[CategoryOut]
    seeded: bool
    public_categories: int


class AnswerOut(BaseModel):
    key: str
    label: str
    value: str


class RequestListItem(ORMModel):
    id: uuid.UUID
    category_title: str
    item_title: str
    contact_name: str
    contact_phone: str
    status: str
    source: str
    telegram_username: str | None = None
    telegram_id: int | None = None
    created_at: datetime
    updated_at: datetime


class RequestOut(RequestListItem):
    answers: list[AnswerOut]
    admin_note: str


class RequestUpdate(BaseModel):
    status: RequestStatus | None = None
    admin_note: str | None = Field(default=None, max_length=2000)


class RequestCounters(BaseModel):
    new: int
    contacted: int
    quoted: int
    won: int
    lost: int
    cancelled: int
    total: int
