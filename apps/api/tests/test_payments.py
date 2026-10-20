from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.job import ScheduledJob
from app.models.notification import Notification
from app.models.payment import Payment
from app.worker.runner import Worker
from tests.helpers import (
    activate_employer,
    approve_first_member,
    create_project,
    make_jobs_due,
    run_worker,
)


def _project_with_employer(admin_client: TestClient) -> dict:
    project = create_project(admin_client, name="پروژه مالی")
    activate_employer(client=admin_client, code=project["license_code"], telegram_id=810001)
    approve_first_member(admin_client, project["id"])
    return project


def _create_payment(admin_client: TestClient, project_id: str, **overrides) -> dict:
    payload = {
        "title": "پیش پرداخت طراحی",
        "amount_minor": 5_000_000,
        "currency": "IRT",
        "due_at": (utcnow() + timedelta(days=10)).isoformat(),
        "notes": "پرداخت مرحله اول",
    }
    payload.update(overrides)
    response = admin_client.post(f"/api/v1/projects/{project_id}/payments", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_payment_creation_and_reminder_scheduling(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه مالی")
    payment = _create_payment(admin_client, project["id"])
    assert payment["amount_minor"] == 5_000_000
    assert payment["currency"] == "IRT"
    assert payment["status"] == "unpaid"
    assert payment["is_overdue"] is False
    assert payment["next_reminder_at"] is not None

    with SessionLocal() as db:
        job = db.scalar(
            select(ScheduledJob).where(
                ScheduledJob.kind == "payment_reminder",
                ScheduledJob.payload["payment_id"].astext == payment["id"],
            )
        )
        assert job is not None
        assert job.status == "pending"


def test_mark_paid_cancels_reminder_and_blocks_edit(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه مالی")
    payment = _create_payment(admin_client, project["id"])
    mark_paid = admin_client.post(f"/api/v1/payments/{payment['id']}/mark-paid")
    assert mark_paid.status_code == 200, mark_paid.text
    paid = mark_paid.json()
    assert paid["status"] == "paid"
    assert paid["paid_at"] is not None
    assert paid["next_reminder_at"] is None

    with SessionLocal() as db:
        job = db.scalar(
            select(ScheduledJob).where(
                ScheduledJob.kind == "payment_reminder",
                ScheduledJob.payload["payment_id"].astext == payment["id"],
            )
        )
        assert job is not None
        assert job.status == "cancelled"

    edit = admin_client.patch(f"/api/v1/payments/{payment['id']}", json={"title": "تغییر عنوان"})
    assert edit.status_code == 409
    cancel = admin_client.post(f"/api/v1/payments/{payment['id']}/cancel")
    assert cancel.status_code == 409


def test_cancel_payment(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه مالی")
    payment = _create_payment(admin_client, project["id"])
    cancel = admin_client.post(f"/api/v1/payments/{payment['id']}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"
    assert cancel.json()["cancelled_at"] is not None
    mark_paid = admin_client.post(f"/api/v1/payments/{payment['id']}/mark-paid")
    assert mark_paid.status_code == 409


def test_due_date_change_reschedules_reminder(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه مالی")
    payment = _create_payment(admin_client, project["id"])
    with SessionLocal() as db:
        before = db.scalar(
            select(ScheduledJob).where(
                ScheduledJob.payload["payment_id"].astext == payment["id"],
                ScheduledJob.status == "pending",
            )
        )
        assert before is not None
        before_id = str(before.id)

    new_due = (utcnow() + timedelta(days=20)).isoformat()
    update = admin_client.patch(f"/api/v1/payments/{payment['id']}", json={"due_at": new_due})
    assert update.status_code == 200, update.text
    with SessionLocal() as db:
        old = db.get(ScheduledJob, before_id)
        assert old is not None
        assert old.status == "cancelled"
        pending = db.scalars(
            select(ScheduledJob).where(
                ScheduledJob.payload["payment_id"].astext == payment["id"],
                ScheduledJob.status == "pending",
            )
        ).all()
        assert len(pending) == 1


def test_overdue_flag_and_validation(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه مالی")
    overdue = _create_payment(
        admin_client,
        project["id"],
        title="پرداخت معوق",
        due_at=(utcnow() - timedelta(days=2)).isoformat(),
    )
    assert overdue["is_overdue"] is True
    assert overdue["next_reminder_at"] is None

    invalid_amount = admin_client.post(
        f"/api/v1/projects/{project['id']}/payments",
        json={
            "title": "نامعتبر",
            "amount_minor": 0,
            "currency": "IRT",
            "due_at": (utcnow() + timedelta(days=3)).isoformat(),
        },
    )
    assert invalid_amount.status_code == 422
    invalid_currency = admin_client.post(
        f"/api/v1/projects/{project['id']}/payments",
        json={
            "title": "نامعتبر",
            "amount_minor": 1000,
            "currency": "GBP",
            "due_at": (utcnow() + timedelta(days=3)).isoformat(),
        },
    )
    assert invalid_currency.status_code == 422


def test_worker_sends_financial_reminder(admin_client: TestClient, mock_adapter) -> None:
    project = _project_with_employer(admin_client)
    payment = _create_payment(
        admin_client,
        project["id"],
        title="پرداخت مرحله دوم",
        amount_minor=2_500_000,
        due_at=(utcnow() + timedelta(days=2)).isoformat(),
    )
    run_worker(mock_adapter)
    reminders = [
        message["text"] for message in mock_adapter.sent if "یادآوری پرداخت" in message["text"]
    ]
    assert reminders, mock_adapter.sent
    text = reminders[-1]
    assert "2,500,000 تومان" in text
    # The reminder text comes from the editable template, not a hard-coded string.
    assert "یادآوری پرداخت برای پروژه" in text
    assert "ارسال رسید" in text
    assert "تایید تراکنش بانکی" in text

    with SessionLocal() as db:
        notifications = db.scalars(
            select(Notification).where(Notification.project_id == project["id"])
        ).all()
        assert len(notifications) == 1
        assert notifications[0].type == "financial"
        assert notifications[0].status == "sent"
        payment_row = db.get(Payment, uuid.UUID(payment["id"]))
        assert payment_row is not None
        assert payment_row.status == "unpaid"

    repeated = admin_client.get(f"/api/v1/projects/{project['id']}/payments").json()
    assert repeated["total"] == 1


def test_settled_payment_never_gets_reminder(admin_client: TestClient, mock_adapter) -> None:
    project = _project_with_employer(admin_client)
    payment = _create_payment(
        admin_client,
        project["id"],
        title="پرداخت تسویه شده",
        due_at=(utcnow() + timedelta(days=2)).isoformat(),
    )
    admin_client.post(f"/api/v1/payments/{payment['id']}/mark-paid")

    # Drain the approval welcome job, then simulate a stale reminder that
    # survived cancellation.
    run_worker(mock_adapter)
    mock_adapter.sent.clear()
    with SessionLocal() as db:
        job = db.scalar(
            select(ScheduledJob).where(
                ScheduledJob.kind == "payment_reminder",
                ScheduledJob.payload["payment_id"].astext == payment["id"],
            )
        )
        assert job is not None
        job.status = "pending"
        db.commit()

    make_jobs_due()
    Worker(settings=get_settings(), adapter=mock_adapter).run_once(max_batches=5)
    assert not mock_adapter.sent

    with SessionLocal() as db:
        notifications = db.scalars(
            select(Notification).where(Notification.project_id == project["id"])
        ).all()
        assert notifications == []
        fresh = db.get(Payment, uuid.UUID(payment["id"]))
        assert fresh is not None and fresh.status == "paid"
