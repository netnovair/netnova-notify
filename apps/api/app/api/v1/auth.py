from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import (
    AdminContext,
    client_ip,
    dev_bearer_enabled,
    get_admin_context,
    is_dev_preview_request,
    verify_browser_origin,
)
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth import AdminOut, LoginRequest, SessionOut
from app.services.auth import COOKIE_NAME, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _cookie_policy(request: Request) -> dict[str, object]:
    """Cookie attributes for the current request.

    Production stays on the strict default (HttpOnly, SameSite=Lax, Secure per
    configuration). A development request served over HTTPS (for example a hosted
    preview inside another site) gets ``SameSite=None; Secure; Partitioned``.
    """
    settings = get_settings()
    if settings.environment == "development":
        forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
        origin = (request.headers.get("origin") or "").strip()
        if origin.startswith("https://") or forwarded_proto == "https":
            return {"secure": True, "samesite": "none", "partitioned": True}
        if is_dev_preview_request(request):
            return {"secure": True, "samesite": "none", "partitioned": True}
    return {
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "partitioned": False,
    }


def _append_partitioned(response: Response) -> None:
    """Emit ``Partitioned`` on Python < 3.14.

    ``http.cookies.Morsel`` only understands the partitioned flag from Python
    3.14, so Starlette raises for older interpreters. Appending the attribute is
    equivalent because this response sets at most one cookie.
    """
    raw = response.headers.get("set-cookie")
    if raw and "partitioned" not in raw.lower():
        response.headers["set-cookie"] = f"{raw}; Partitioned"


def _set_session_cookie(response: Response, token: str, request: Request) -> None:
    settings = get_settings()
    policy = _cookie_policy(request)
    partitioned = bool(policy.pop("partitioned", False))
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        path="/",
        **policy,
    )
    if partitioned:
        _append_partitioned(response)


@router.post("/login", response_model=SessionOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionOut:
    verify_browser_origin(request)
    token, csrf_token, session = AuthService.login(
        db,
        email=payload.email,
        password=payload.password,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    dev_token = token if dev_bearer_enabled() else None
    logger.info("login ok admin=%s dev_token_issued=%s", session.admin_id, int(bool(dev_token)))
    _set_session_cookie(response, token, request)
    return SessionOut(
        admin=AdminOut.model_validate(session.admin),
        csrf_token=csrf_token,
        expires_at=session.expires_at,
        # Development only: a preview iframe may block the session cookie, so the
        # panel falls back to a Bearer header. Always null outside development.
        dev_session_token=dev_token,
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    ctx: AdminContext = Depends(get_admin_context),
    db: Session = Depends(get_db),
) -> dict:
    AuthService.logout(db, ctx.session, ctx.admin)
    policy = _cookie_policy(request)
    partitioned = bool(policy.pop("partitioned", False))
    response.delete_cookie(COOKIE_NAME, path="/", **policy)
    if partitioned:
        _append_partitioned(response)
    return {"ok": True}


@router.get("/me", response_model=SessionOut)
def me(
    ctx: AdminContext = Depends(get_admin_context),
) -> SessionOut:
    return SessionOut(
        admin=AdminOut.model_validate(ctx.admin),
        csrf_token=ctx.session.csrf_token,
        expires_at=ctx.session.expires_at,
    )


@router.get("/bootstrap-status")
def bootstrap_status(db: Session = Depends(get_db)) -> dict:
    return {"admin_configured": AuthService.admin_configured(db)}
