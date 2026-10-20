from fastapi import APIRouter

from app.api.v1 import (
    accounting,
    admins,
    audit,
    auth,
    catalog,
    channels,
    dashboard,
    diagnostics,
    health,
    licenses,
    members,
    notifications,
    orders,
    payments,
    projects,
    telegram,
    tickets,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(dashboard.router)
api_router.include_router(projects.router)
api_router.include_router(licenses.router)
api_router.include_router(members.router)
api_router.include_router(notifications.router)
api_router.include_router(payments.router)
api_router.include_router(accounting.router)
api_router.include_router(audit.router)
api_router.include_router(telegram.router)
api_router.include_router(tickets.router)
api_router.include_router(admins.router)
api_router.include_router(channels.router)
api_router.include_router(catalog.router)
api_router.include_router(orders.router)

from app.core.config import get_settings  # noqa: E402

if get_settings().environment == "development":
    # Browser diagnostics are a development aid only; production never exposes them.
    api_router.include_router(diagnostics.router)
