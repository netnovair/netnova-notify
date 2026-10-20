from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import forbidden, unauthorized
from app.db.session import get_db
from app.models.admin import AdminSession, AdminUser
from app.services.auth import COOKIE_NAME, AuthService


@dataclass
class AdminContext:
    session: AdminSession
    admin: AdminUser

    @property
    def actor(self):
        from app.services.audit import Actor

        return Actor(type="admin", id=self.admin.id, label=self.admin.display_name)


def dev_bearer_enabled() -> bool:
    """Development-only fallback for browsers that block preview cookies.

    A hosted development preview is rendered inside a third-party iframe, where
    browsers may refuse to store or send the session cookie at all. In
    development the API therefore also accepts the session token as a Bearer
    header. Production and test environments never enable this.
    """
    return get_settings().environment == "development"


def is_dev_preview_request(request: Request) -> bool:
    """Best-effort detection of a hosted development preview host.

    Only used to pick cookie attributes; authentication never depends on it.
    """
    settings = get_settings()
    if settings.environment != "development" or not settings.dev_preview_origin_regex:
        return False
    candidates: list[str] = []
    origin = request.headers.get("origin")
    if origin:
        candidates.append(origin.rstrip("/"))
    for header in ("x-forwarded-host", "host"):
        host = request.headers.get(header)
        if host:
            candidates.append(f"https://{host.split(',')[0].strip()}")
    try:
        return any(
            re.fullmatch(settings.dev_preview_origin_regex, candidate) for candidate in candidates
        )
    except re.error:
        return False


#: Custom header used by the development preview. Some hosting proxies strip or
#: rewrite the standard ``Authorization`` header, so the panel sends the same
#: session token through this header as well.
DEV_SESSION_HEADER = "x-nn-session"


def session_token_from_headers(request: Request) -> str | None:
    """Session token supplied by a request header, if any.

    The development preview sends the token twice (custom header + Bearer) because
    a proxy may remove one of them. The standard header is kept so normal API
    clients work unchanged.
    """
    custom = request.headers.get(DEV_SESSION_HEADER)
    if custom and custom.strip():
        return custom.strip()
    header = request.headers.get("authorization")
    if not header:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = value.strip()
    return token or None


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


def get_admin_context(
    request: Request,
    db: Session = Depends(get_db),
) -> AdminContext:
    raw_token = request.cookies.get(COOKIE_NAME)
    result = AuthService.authenticate(db, raw_token)
    if result is None:
        # Development fallback: a preview iframe may drop the cookie entirely, and a
        # stale leftover cookie must not hide a valid Bearer token. Production and
        # test environments never accept header-only sessions.
        bearer = session_token_from_headers(request)
        if bearer and dev_bearer_enabled():
            result = AuthService.authenticate(db, bearer)
    if result is None:
        raise unauthorized()
    session, admin = result
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        AuthService.verify_csrf(session, request.headers.get("x-csrf-token"))
    return AdminContext(session=session, admin=admin)


def verify_browser_origin(request: Request) -> None:
    """Blocks login CSRF from foreign origins when a browser sends Origin."""
    origin = request.headers.get("origin")
    if not origin:
        return
    settings = get_settings()
    normalized = origin.rstrip("/")
    if normalized in settings.allowed_origins:
        return
    if normalized == settings.next_public_site_url.rstrip("/"):
        return
    if settings.environment == "development" and settings.dev_preview_origin_regex:
        try:
            if re.fullmatch(settings.dev_preview_origin_regex, normalized):
                return
        except re.error:
            pass
    raise forbidden("مبدا درخواست معتبر نیست.")
