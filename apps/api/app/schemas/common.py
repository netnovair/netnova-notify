from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


def ensure_timezone(value: datetime | None) -> datetime | None:
    """Naive inputs are interpreted as Tehran local time (the product timezone)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=ZoneInfo("Asia/Tehran"))
    return value


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


def pages_for(total: int, page_size: int) -> int:
    if total <= 0:
        return 0
    return (total + page_size - 1) // page_size
