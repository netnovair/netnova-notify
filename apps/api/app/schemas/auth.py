from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class AdminOut(ORMModel):
    id: uuid.UUID
    email: str
    display_name: str
    last_login_at: datetime | None = None


class SessionOut(BaseModel):
    admin: AdminOut
    csrf_token: str
    expires_at: datetime
    dev_session_token: str | None = Field(
        default=None,
        description=(
            "Development preview only. Returned when ENVIRONMENT=development and the "
            "request host matches DEV_PREVIEW_ORIGIN_REGEX, so the admin panel can keep "
            "working when the browser blocks the session cookie inside a third-party "
            "iframe. Always null in staging and production."
        ),
    )
