from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.audit import AuditLogOut


class DashboardOut(BaseModel):
    projects_total: int
    projects_active: int
    notifications_total: int
    queued_notifications: int
    failed_notifications: int
    open_payments: int
    open_payments_amount_by_currency: dict[str, int]
    pending_members: int
    license_attention: int
    recent_activity: list[AuditLogOut]
    generated_at: datetime


class WorkerStatus(BaseModel):
    status: str
    last_seen_at: datetime | None
    hostname: str | None


class TelegramStatus(BaseModel):
    mode: str
    bot_configured: bool
    webhook_secret_configured: bool
    last_update_at: datetime | None
    webhook_path: str


class DatabaseStatus(BaseModel):
    status: str
    dialect: str
    latency_ms: int | None


class SystemStatusOut(BaseModel):
    environment: str
    server_time: datetime
    database: DatabaseStatus
    worker: WorkerStatus
    telegram: TelegramStatus
    timezone: str
    payment_reminder_days_before: int
    session_ttl_hours: int
    https_required: bool
    site_url: str
    pending_jobs: int
    failed_jobs: int
