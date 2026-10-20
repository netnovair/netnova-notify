from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.job import ScheduledJob


class JobRepository:
    @staticmethod
    def enqueue(
        db: Session,
        *,
        kind: str,
        payload: dict,
        run_at: datetime,
        now: datetime,
        max_attempts: int,
        dedupe_key: str | None = None,
    ) -> ScheduledJob | None:
        """Insert a job. Returns None when dedupe_key already exists (idempotent)."""
        values = {
            "kind": kind,
            "payload": payload,
            "status": "pending",
            "run_at": run_at,
            "attempts": 0,
            "max_attempts": max_attempts,
            "created_at": now,
            "updated_at": now,
            "dedupe_key": dedupe_key,
        }
        if dedupe_key:
            statement = (
                pg_insert(ScheduledJob)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["dedupe_key"])
                .returning(ScheduledJob.id)
            )
            job_id = db.scalar(statement)
            if job_id is None:
                return None
            return db.get(ScheduledJob, job_id)
        job = ScheduledJob(**values)
        db.add(job)
        db.flush()
        return job

    @staticmethod
    def get(db: Session, job_id: uuid.UUID, *, lock: bool = False) -> ScheduledJob | None:
        query = select(ScheduledJob).where(ScheduledJob.id == job_id)
        if lock:
            query = query.with_for_update()
        return db.scalar(query)

    @staticmethod
    def cancel(db: Session, job_id: uuid.UUID | None, now: datetime) -> bool:
        if job_id is None:
            return False
        result = db.execute(
            update(ScheduledJob)
            .where(ScheduledJob.id == job_id, ScheduledJob.status == "pending")
            .values(status="cancelled", updated_at=now, finished_at=now)
        )
        return bool(result.rowcount)

    @staticmethod
    def claim_batch(
        db: Session,
        *,
        worker_id: str,
        limit: int,
        now: datetime,
        stale_before: datetime,
    ) -> list[uuid.UUID]:
        # Recover jobs whose worker died while processing them.
        db.execute(
            update(ScheduledJob)
            .where(
                ScheduledJob.status == "processing",
                ScheduledJob.locked_at.is_not(None),
                ScheduledJob.locked_at < stale_before,
            )
            .values(status="pending", locked_at=None, locked_by=None, updated_at=now)
        )
        ids = list(
            db.scalars(
                select(ScheduledJob.id)
                .where(ScheduledJob.status == "pending", ScheduledJob.run_at <= now)
                .order_by(ScheduledJob.run_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
        )
        if not ids:
            db.commit()
            return []
        db.execute(
            update(ScheduledJob)
            .where(ScheduledJob.id.in_(ids))
            .values(
                status="processing",
                locked_at=now,
                locked_by=worker_id,
                attempts=ScheduledJob.attempts + 1,
                updated_at=now,
            )
        )
        db.commit()
        return ids

    @staticmethod
    def pending_count(db: Session) -> int:
        return int(
            db.scalar(select(func.count(ScheduledJob.id)).where(ScheduledJob.status == "pending"))
            or 0
        )

    @staticmethod
    def failed_count(db: Session) -> int:
        return int(
            db.scalar(select(func.count(ScheduledJob.id)).where(ScheduledJob.status == "failed"))
            or 0
        )

    @staticmethod
    def next_payment_reminder(db: Session, payment_id: uuid.UUID) -> ScheduledJob | None:
        return db.scalar(
            select(ScheduledJob)
            .where(
                ScheduledJob.kind == "payment_reminder",
                ScheduledJob.status == "pending",
                ScheduledJob.payload["payment_id"].astext == str(payment_id),
            )
            .order_by(ScheduledJob.run_at)
            .limit(1)
        )

    @staticmethod
    def backoff_seconds(attempts: int, base: int) -> int:
        return min(base * (2 ** max(attempts - 1, 0)), 3600)
