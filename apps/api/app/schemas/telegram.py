from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class TelegramWebhookResponse(BaseModel):
    ok: bool = True
    duplicate: bool = False


class TelegramUpdatePayload(BaseModel):
    """Loose model: Telegram updates evolve; we validate the fields we consume."""

    model_config = ConfigDict(extra="allow")

    update_id: int
    message: dict[str, Any] | None = None
    callback_query: dict[str, Any] | None = None
