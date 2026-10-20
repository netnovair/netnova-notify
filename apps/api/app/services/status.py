from __future__ import annotations

import time
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import utcnow
from app.models.system import SystemState
from app.repositories.jobs import JobRepository
from app.schemas.dashboard import (
    DatabaseStatus,
    SystemStatusOut,
    TelegramStatus,
    WorkerStatus,
)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class StatusService:
    @staticmethod
    def database_status(db: Session) -> DatabaseStatus:
        started = time.perf_counter()
        try:
            db.execute(text("SELECT 1"))
            latency = int((time.perf_counter() - started) * 1000)
            return DatabaseStatus(
                status="ok",
                dialect=db.bind.dialect.name if db.bind else "postgresql",
                latency_ms=latency,
            )
        except Exception:  # noqa: BLE001
            return DatabaseStatus(status="error", dialect="postgresql", latency_ms=None)

    @staticmethod
    def worker_status(db: Session, now: datetime | None = None) -> WorkerStatus:
        now = now or utcnow()
        state = db.get(SystemState, "worker_heartbeat")
        if state is None:
            return WorkerStatus(status="unknown", last_seen_at=None, hostname=None)
        at = _parse_dt(state.value.get("at"))
        hostname = state.value.get("hostname")
        if at is None:
            return WorkerStatus(status="unknown", last_seen_at=None, hostname=hostname)
        status = "online" if now - at <= timedelta(seconds=90) else "offline"
        return WorkerStatus(status=status, last_seen_at=at, hostname=hostname)

    @staticmethod
    def telegram_status(db: Session) -> TelegramStatus:
        settings = get_settings()
        state = db.get(SystemState, "telegram_last_update_at")
        last_update = _parse_dt(state.value.get("at")) if state else None
        return TelegramStatus(
            mode=settings.telegram_mode,
            bot_configured=bool(settings.telegram_bot_token),
            webhook_secret_configured=bool(settings.telegram_webhook_secret),
            last_update_at=last_update,
            webhook_path="/api/v1/telegram/webhook",
        )

    @staticmethod
    def queue_state(
        pending: int, worker: WorkerStatus, oldest: datetime | None, now: datetime
    ) -> tuple[str, int | None]:
        """Honest queue state for the panel.

        ``stalled`` is the important one: jobs are waiting but nothing is
        claiming them, which is exactly the failure mode that made announcements
        appear to do nothing.
        """
        oldest_seconds = int((now - oldest).total_seconds()) if oldest else None
        if pending == 0:
            return "idle", oldest_seconds
        if worker.status == "online":
            return "draining", oldest_seconds
        return "stalled", oldest_seconds

    @staticmethod
    def get(db: Session, settings: Settings | None = None) -> SystemStatusOut:
        settings = settings or get_settings()
        now = utcnow()
        worker = StatusService.worker_status(db, now)
        pending = JobRepository.pending_count(db)
        queue_status, oldest_seconds = StatusService.queue_state(
            pending, worker, JobRepository.oldest_pending_at(db), now
        )
        return SystemStatusOut(
            environment=settings.environment,
            server_time=now,
            database=StatusService.database_status(db),
            worker=worker,
            telegram=StatusService.telegram_status(db),
            timezone=settings.tehran_timezone,
            payment_reminder_days_before=settings.payment_reminder_days_before,
            session_ttl_hours=settings.session_ttl_hours,
            https_required=settings.environment == "production" or settings.cookie_secure,
            site_url=settings.next_public_site_url,
            pending_jobs=pending,
            failed_jobs=JobRepository.failed_count(db),
            embedded_worker=settings.embedded_worker,
            oldest_pending_seconds=oldest_seconds,
            queue_status=queue_status,
        )
