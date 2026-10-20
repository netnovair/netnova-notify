from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.adapters.telegram.base import TelegramAdapter
from app.adapters.telegram.factory import get_telegram_adapter
from app.core.config import Settings, get_settings
from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.job import ScheduledJob
from app.models.system import SystemState
from app.repositories.jobs import JobRepository
from app.services.audit import Actor, AuditService
from app.services.notifications import RetryableDeliveryError
from app.worker.handlers import HANDLERS, finalize_notification_failure

logger = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        settings: Settings | None = None,
        adapter: TelegramAdapter | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.adapter = adapter or get_telegram_adapter()
        self.worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self._stop = threading.Event()

    # ------------------------------------------------------------------
    def request_stop(self, *_: object) -> None:
        logger.info("Shutdown requested for worker %s", self.worker_id)
        self._stop.set()

    def run_forever(self) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)
        logger.info("Worker %s started (adapter=%s)", self.worker_id, self.adapter.mode)
        while not self._stop.is_set():
            processed = self.run_once()
            if processed == 0:
                self._stop.wait(self.settings.worker_poll_interval_seconds)
        logger.info("Worker %s stopped", self.worker_id)

    def run_once(self, max_batches: int = 1) -> int:
        processed_total = 0
        for _ in range(max_batches):
            self._heartbeat()
            now = utcnow()
            stale_before = now - timedelta(seconds=self.settings.worker_stale_seconds)
            claim_db = SessionLocal()
            try:
                ids = JobRepository.claim_batch(
                    claim_db,
                    worker_id=self.worker_id,
                    limit=self.settings.worker_batch_size,
                    now=now,
                    stale_before=stale_before,
                )
            finally:
                claim_db.close()
            if not ids:
                break
            for job_id in ids:
                self._process(job_id)
                processed_total += 1
        return processed_total

    # ------------------------------------------------------------------
    def _heartbeat(self) -> None:
        now = utcnow()
        db = SessionLocal()
        try:
            state = db.get(SystemState, "worker_heartbeat")
            value = {
                "at": now.isoformat(),
                "hostname": socket.gethostname(),
                "pid": os.getpid(),
                "worker_id": self.worker_id,
                "adapter": self.adapter.mode,
            }
            if state is None:
                db.add(SystemState(key="worker_heartbeat", value=value, updated_at=now))
            else:
                state.value = value
                state.updated_at = now
            db.commit()
        except Exception:  # noqa: BLE001 - heartbeat must never kill the worker
            db.rollback()
            logger.warning("Worker heartbeat failed", exc_info=True)
        finally:
            db.close()

    def _process(self, job_id: uuid.UUID) -> None:
        db = SessionLocal()
        try:
            job = JobRepository.get(db, job_id, lock=True)
            if job is None or job.status != "processing":
                return
            handler = HANDLERS.get(job.kind)
            if handler is None:
                self._handle_unexpected(db, job_id, f"Unknown job kind: {job.kind}")
                return
            try:
                handler(db, job, self.adapter, self.settings)
            except RetryableDeliveryError as exc:
                self._handle_retryable(db, job, str(exc))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Job %s (%s) failed", job.id, job.kind)
                db.rollback()
                self._handle_unexpected(db, job_id, f"{type(exc).__name__}: {exc}")
            else:
                now = utcnow()
                job.status = "done"
                job.finished_at = now
                job.locked_at = None
                job.locked_by = None
                job.updated_at = now
                db.commit()
        finally:
            db.close()

    def _handle_retryable(self, db: Session, job: ScheduledJob, error: str) -> None:
        now = utcnow()
        job.last_error = error[:1000]
        job.updated_at = now
        job.locked_at = None
        job.locked_by = None
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.finished_at = now
            finalize_notification_failure(db, job, error)
            AuditService.record(
                db,
                actor=Actor(type="system", label="worker"),
                action="job.failed",
                entity_type="scheduled_job",
                entity_id=job.id,
                project_id=self._project_id(job),
                context={"kind": job.kind, "attempts": job.attempts, "error": error[:500]},
                now=now,
            )
            logger.error("Job %s failed permanently after %s attempts", job.id, job.attempts)
        else:
            delay = JobRepository.backoff_seconds(
                job.attempts, self.settings.job_backoff_base_seconds
            )
            job.status = "pending"
            job.run_at = now + timedelta(seconds=delay)
            logger.warning(
                "Job %s scheduled for retry in %ss (attempt %s/%s)",
                job.id,
                delay,
                job.attempts,
                job.max_attempts,
            )
        db.commit()

    def _handle_unexpected(self, db: Session, job_id: uuid.UUID, error: str) -> None:
        now = utcnow()
        try:
            fresh = JobRepository.get(db, job_id, lock=True)
            if fresh is None:
                return
            fresh.last_error = error[:1000]
            fresh.updated_at = now
            fresh.locked_at = None
            fresh.locked_by = None
            if fresh.attempts >= fresh.max_attempts:
                fresh.status = "failed"
                fresh.finished_at = now
                finalize_notification_failure(db, fresh, error)
                AuditService.record(
                    db,
                    actor=Actor(type="system", label="worker"),
                    action="job.failed",
                    entity_type="scheduled_job",
                    entity_id=fresh.id,
                    project_id=self._project_id(fresh),
                    context={
                        "kind": fresh.kind,
                        "attempts": fresh.attempts,
                        "error": error[:500],
                    },
                    now=now,
                )
            else:
                delay = JobRepository.backoff_seconds(
                    fresh.attempts, self.settings.job_backoff_base_seconds
                )
                fresh.status = "pending"
                fresh.run_at = now + timedelta(seconds=delay)
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("Could not reschedule failed job %s", job_id)

    @staticmethod
    def _project_id(job: ScheduledJob) -> uuid.UUID | None:
        raw = job.payload.get("project_id")
        if not raw:
            return None
        try:
            return uuid.UUID(str(raw))
        except ValueError:
            return None
