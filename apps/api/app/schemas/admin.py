from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class AdminOut(ORMModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    last_login_at: datetime | None = None
    last_password_change_at: datetime | None = None
    created_at: datetime


class AdminCreate(BaseModel):
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()


class AdminUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    is_active: bool | None = None


class AdminPasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class AdminPasswordReset(BaseModel):
    """Confirmation payload: the admin must retype the target email."""

    confirm_email: str = Field(min_length=5, max_length=255)


class TemporaryPasswordOut(BaseModel):
    admin_id: uuid.UUID
    temporary_password: str
    message: str


class ChannelStateOut(BaseModel):
    key: str
    label: str
    description: str
    recipient_hint: str
    supports_keyboard: bool
    beta: bool
    docs_url: str | None = None
    configured: bool
    mode: str


class FeatureCatalogItem(BaseModel):
    key: str
    label: str
    description: str
    implemented: bool
    default_enabled: bool
    action: str | None
    settings_schema: dict = {}
