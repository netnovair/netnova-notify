from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.api.v1 import health
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.db.session import SessionLocal
from app.services.auth import AuthService

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()
# Interactive API docs expose the whole schema; keep them out of production.
docs_enabled = settings.environment != "production"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime()
    db = SessionLocal()
    try:
        try:
            AuthService.bootstrap_admin(db)
        except (OperationalError, ProgrammingError):
            db.rollback()
            logger.warning(
                "Database schema is not ready. Run `alembic upgrade head` before using the API."
            )
    finally:
        db.close()
    yield


app = FastAPI(
    title="NetNova Notify API",
    version="0.1.0",
    description="Central notification management API for NetNova Digital Marketing Agency.",
    docs_url="/api/docs" if docs_enabled else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if docs_enabled else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Requested-With", "X-NN-Session"],
    max_age=600,
)

register_exception_handlers(app)


@app.middleware("http")
async def dev_auth_diagnostics(request, call_next):
    """Log *how* a development request authenticated (never the token itself).

    Hosted previews run inside a third-party iframe, where browsers may silently
    drop cookies. These three booleans are enough to tell a cookie problem from a
    client-side bug without ever writing a secret to the log.
    """
    response = await call_next(request)
    if settings.environment == "development" and request.url.path.startswith("/api/v1"):
        logger.info(
            "auth-shape path=%s cookie=%s bearer=%s xsess=%s status=%s",
            request.url.path,
            int("nn_session" in request.cookies),
            int(bool(request.headers.get("authorization"))),
            int(bool(request.headers.get("x-nn-session"))),
            response.status_code,
        )
    return response


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    if request.url.path.startswith("/api/") or request.url.path.startswith("/health/"):
        # API responses contain private operational data and must not be cached
        # by browsers, proxies or the service worker.
        response.headers["Cache-Control"] = "no-store"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(api_router, prefix="/api/v1")
# Deployment health checks commonly probe /health/* at the root.
app.include_router(health.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    payload = {
        "service": "NetNova Notify API",
        "version": app.version,
        "health": "/api/v1/health/live",
    }
    if docs_enabled:
        payload["docs"] = "/api/docs"
    return payload
