"""Development-only browser diagnostics for the hosted preview.

A hosted preview runs inside an iframe on another origin. Browsers may then treat
the session cookie and every storage API as unavailable, so the panel can log in
successfully and still be unable to read any data. This endpoint receives a small,
non-sensitive report from the panel so the backend log explains what the browser
actually allows.

It is registered only when ``ENVIRONMENT=development`` and never stores anything.
No cookie value, token, URL path or personal data is accepted.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

_ALLOWED_FLAGS = {
    "in_iframe",
    "opaque_origin",
    "secure_context",
    "cookies_enabled",
    "session_storage",
    "local_storage",
    "window_name",
    "has_dev_token",
    "attached_bearer",
    "api_ok",
}


class ClientReport(BaseModel):
    """Whitelisted facts; ``extra="forbid"`` blocks accidental data leaks."""

    model_config = {"extra": "forbid"}

    flags: dict[str, bool] = Field(default_factory=dict)
    me_status: int = 0
    user_agent: str = ""


@router.post("/client")
def client_report(payload: ClientReport) -> dict:
    flags = {key: bool(value) for key, value in payload.flags.items() if key in _ALLOWED_FLAGS}
    logger.info(
        "preview-diagnostics me_status=%s flags=%s agent=%r",
        payload.me_status,
        " ".join(f"{key}={int(value)}" for key, value in sorted(flags.items())),
        payload.user_agent[:120],
    )
    return {"ok": True}
