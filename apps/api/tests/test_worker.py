from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.telegram.base import (
    PermanentTelegramError,
    SendResult,
    TemporaryTelegramError,
    UnknownTelegramError,
)
from app.adapters.telegram.mock import MockTelegramAdapter
from app.core.config import get_settings
from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.job import ScheduledJob
from app.models.notification import DeliveryAttempt, Notification
from app.repositories.jobs import JobRepository
from app.worker.runner import Worker
from tests.helpers import (
    activate_employer,
    approve_first_member,
    create_project,
    make_jobs_due,
)

settings = get_settings()


class SequenceAdapter(MockTelegramAdapter):
    def __init__(self, errors: list[Exception]) -> None:
        super().__init__()
        self.errors = list(errors)
        self.calls = 0

    def send_message(self, chat_id: int, text: str, keyboard: dict | None = None) -> SendResult:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return super().send_message(chat_id, text, keyboard)


class CountingAdapter(MockTelegramAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def send_message(self, chat_id: int, text: str, keyboard: dict | None = None) -> SendResult:
        self.calls += 1
        return super().send_message(chat_id, text, keyboard)


def _project_with_employer(admin_client: TestClient) -> dict:
    project = create_project(admin_client, name="پروژه ورکر")
    activate_employer(client=admin_client, code=project["license_code"], telegram_id=830001)
    approve_first_member(admin_client, project["id"])
    # Drain the approval welcome job so notification assertions are isolated.
    make_jobs_due()
    Worker(settings=settings, adapter=MockTelegramAdapter()).run_once(max_batches=5)
    return project


def _create_notification(admin_client: TestClient, project_id: str) -> dict:
    response = admin_client.post(
        f"/api/v1/projects/{project_id}/notifications",
        json={"title": "اطلاعیه ورکر", "body": "متن تست"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_claiming_is_exclusive() -> None:
    now = utcnow()
    with SessionLocal() as db:
        job = JobRepository.enqueue(
            db,
            kind="notification_send",
            payload={"project_id": None},
            run_at=now,
            now=now,
            max_attempts=2,
        )
        db.commit()
        job_id = str(job.id)

    with SessionLocal() as db:
        first = JobRepository.claim_batch(
            db,
            worker_id="worker-a",
            limit=5,
            now=utcnow(),
            stale_before=utcnow() - timedelta(seconds=300),
        )
        assert [str(item) for item in first] == [job_id]

    with SessionLocal() as db:
        second = JobRepository.claim_batch(
            db,
            worker_id="worker-b",
            limit=5,
            now=utcnow(),
            stale_before=utcnow() - timedelta(seconds=300),
        )
        assert second == []


def test_stale_processing_job_is_recovered() -> None:
    now = utcnow()
    with SessionLocal() as db:
        job = JobRepository.enqueue(
            db,
            kind="notification_send",
            payload={"project_id": None},
            run_at=now,
            now=now,
            max_attempts=5,
        )
        db.commit()
        job_id = job.id

    with SessionLocal() as db:
        JobRepository.claim_batch(
            db,
            worker_id="dead-worker",
            limit=5,
            now=utcnow(),
            stale_before=utcnow() - timedelta(seconds=300),
        )
        job = db.get(ScheduledJob, job_id)
        assert job is not None
        job.locked_at = utcnow() - timedelta(seconds=600)
        db.commit()

    with SessionLocal() as db:
        recovered = JobRepository.claim_batch(
            db,
            worker_id="new-worker",
            limit=5,
            now=utcnow(),
            stale_before=utcnow() - timedelta(seconds=300),
        )
        assert [str(item) for item in recovered] == [str(job_id)]
        job = db.get(ScheduledJob, job_id)
        assert job is not None
        assert job.attempts == 2
        assert job.locked_by == "new-worker"


def test_temporary_error_is_retried_by_a_restarted_worker(
    admin_client: TestClient,
) -> None:
    project = _project_with_employer(admin_client)
    notification = _create_notification(admin_client, project["id"])
    adapter = SequenceAdapter([TemporaryTelegramError("rate limited", retry_after=1)])

    make_jobs_due()
    Worker(settings=settings, adapter=adapter).run_once(max_batches=5)

    detail = admin_client.get(f"/api/v1/notifications/{notification['id']}").json()
    assert detail["status"] == "retry_wait"
    assert detail["last_error"]
    with SessionLocal() as db:
        job = db.scalar(
            select(ScheduledJob).where(
                ScheduledJob.payload["notification_id"].astext == notification["id"],
                ScheduledJob.kind == "notification_send",
            )
        )
        assert job is not None
        assert job.status == "pending"
        assert job.run_at > utcnow()

    # A new worker instance, after the retry delay, completes the job.
    make_jobs_due()
    Worker(settings=settings, adapter=adapter).run_once(max_batches=5)
    detail = admin_client.get(f"/api/v1/notifications/{notification['id']}").json()
    assert detail["status"] == "sent"
    assert [d["status"] for d in detail["deliveries"]] == ["failed", "sent"]
    assert adapter.calls >= 2


def test_timeout_is_not_automatically_retried(admin_client: TestClient) -> None:
    project = _project_with_employer(admin_client)
    notification = _create_notification(admin_client, project["id"])
    adapter = SequenceAdapter([UnknownTelegramError("timeout")])

    make_jobs_due()
    Worker(settings=settings, adapter=adapter).run_once(max_batches=5)
    detail = admin_client.get(f"/api/v1/notifications/{notification['id']}").json()
    assert detail["status"] == "failed"
    assert "نامشخص" in detail["last_error"]
    assert [d["status"] for d in detail["deliveries"]] == ["unknown"]

    with SessionLocal() as db:
        jobs = db.scalars(
            select(ScheduledJob).where(
                ScheduledJob.payload["notification_id"].astext == notification["id"]
            )
        ).all()
        assert all(job.status in ("done", "cancelled") for job in jobs)

    calls_after_first = adapter.calls
    make_jobs_due()
    Worker(settings=settings, adapter=adapter).run_once(max_batches=5)
    assert adapter.calls == calls_after_first


def test_permanent_error_fails_without_retry(admin_client: TestClient) -> None:
    project = _project_with_employer(admin_client)
    notification = _create_notification(admin_client, project["id"])
    adapter = SequenceAdapter([PermanentTelegramError("bot was blocked")])
    make_jobs_due()
    Worker(settings=settings, adapter=adapter).run_once(max_batches=5)
    detail = admin_client.get(f"/api/v1/notifications/{notification['id']}").json()
    assert detail["status"] == "failed"
    assert adapter.calls == 1
    with SessionLocal() as db:
        job = db.scalar(
            select(ScheduledJob).where(
                ScheduledJob.payload["notification_id"].astext == notification["id"]
            )
        )
        assert job is not None
        assert job.status == "done"


def test_unconfirmed_attempt_from_crash_is_never_resent(
    admin_client: TestClient,
) -> None:
    project = _project_with_employer(admin_client)
    notification = _create_notification(admin_client, project["id"])

    with SessionLocal() as db:
        row = db.get(Notification, uuid.UUID(notification["id"]))
        assert row is not None
        row.status = "sending"
        row.attempt_count = 1
        db.add(
            DeliveryAttempt(
                notification_id=row.id,
                chat_id=830001,
                status="sending",
                attempt_no=1,
                started_at=utcnow(),
                created_at=utcnow(),
            )
        )
        db.commit()

    adapter = CountingAdapter()
    make_jobs_due()
    Worker(settings=settings, adapter=adapter).run_once(max_batches=5)
    assert adapter.calls == 0
    detail = admin_client.get(f"/api/v1/notifications/{notification['id']}").json()
    assert detail["status"] == "failed"
    assert "نامشخص" in detail["last_error"]
    assert detail["deliveries"][0]["status"] == "unknown"


def test_worker_heartbeat_visible_in_status(admin_client: TestClient) -> None:
    adapter = MockTelegramAdapter()
    Worker(settings=settings, adapter=adapter).run_once(max_batches=1)
    status = admin_client.get("/api/v1/system/status")
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["worker"]["status"] == "online"
    assert body["worker"]["last_seen_at"] is not None
    assert body["telegram"]["mode"] == "mock"
    assert body["database"]["status"] == "ok"
    assert body["environment"] == "test"


def test_max_attempts_stops_retrying(admin_client: TestClient) -> None:
    project = _project_with_employer(admin_client)
    notification = _create_notification(admin_client, project["id"])
    errors = [TemporaryTelegramError("rate limited") for _ in range(settings.job_max_attempts)]
    adapter = SequenceAdapter(errors)

    for _ in range(settings.job_max_attempts):
        make_jobs_due()
        Worker(settings=settings, adapter=adapter).run_once(max_batches=5)

    detail = admin_client.get(f"/api/v1/notifications/{notification['id']}").json()
    assert detail["status"] == "failed"
    with SessionLocal() as db:
        job = db.scalar(
            select(ScheduledJob).where(
                ScheduledJob.payload["notification_id"].astext == notification["id"]
            )
        )
        assert job is not None
        assert job.status == "failed"
        assert job.attempts == settings.job_max_attempts
    calls = adapter.calls
    make_jobs_due()
    Worker(settings=settings, adapter=adapter).run_once(max_batches=5)
    assert adapter.calls == calls


def test_unknown_job_kind_fails_safely() -> None:
    now = utcnow()
    with SessionLocal() as db:
        job = JobRepository.enqueue(
            db,
            kind="unknown_kind",
            payload={"project_id": None},
            run_at=now,
            now=now,
            max_attempts=1,
        )
        db.commit()
        job_id = job.id

    Worker(settings=settings, adapter=MockTelegramAdapter()).run_once(max_batches=5)
    with SessionLocal() as db:
        row = db.get(ScheduledJob, job_id)
        assert row is not None
        assert row.status == "failed"
        assert "Unknown job kind" in (row.last_error or "")
