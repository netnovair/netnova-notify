from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.job import ScheduledJob
from tests.helpers import (
    activate_employer,
    approve_first_member,
    create_project,
    run_worker,
)


def _project_with_employer(admin_client: TestClient) -> dict:
    project = create_project(admin_client, name="پروژه اطلاع رسانی")
    activate_employer(client=admin_client, code=project["license_code"], telegram_id=800001)
    approve_first_member(admin_client, project["id"])
    return project


def test_notification_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects/00000000-0000-4000-8000-000000000000/notifications",
        json={"title": "x", "body": "y"},
    )
    assert response.status_code == 401


def test_immediate_notification_is_sent_by_worker(admin_client: TestClient, mock_adapter) -> None:
    project = _project_with_employer(admin_client)
    create = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={"title": "نسخه جدید سایت", "body": "سایت به نسخه جدید به روز شد."},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["status"] == "queued"
    assert body["scheduled_at"] is None

    with SessionLocal() as db:
        job = db.scalar(
            select(ScheduledJob).where(
                ScheduledJob.kind == "notification_send",
                ScheduledJob.payload["notification_id"].astext == body["id"],
            )
        )
        assert job is not None
        assert job.status == "pending"

    run_worker(mock_adapter)
    detail = admin_client.get(f"/api/v1/notifications/{body['id']}").json()
    assert detail["status"] == "sent"
    assert detail["sent_at"] is not None
    assert len(detail["deliveries"]) == 1
    delivery = detail["deliveries"][0]
    assert delivery["status"] == "sent"
    assert delivery["is_mock"] is True
    assert delivery["attempt_no"] == 1
    assert any("نسخه جدید سایت" in message["text"] for message in mock_adapter.sent)

    deliveries = admin_client.get(f"/api/v1/notifications/{body['id']}/deliveries")
    assert deliveries.status_code == 200
    assert len(deliveries.json()) == 1


def test_notification_without_member_fails_honestly(admin_client: TestClient, mock_adapter) -> None:
    project = create_project(admin_client, name="پروژه بدون کارفرما")
    create = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={"title": "اطلاعیه", "body": "متن"},
    )
    assert create.status_code == 201
    run_worker(mock_adapter)
    detail = admin_client.get(f"/api/v1/notifications/{create.json()['id']}").json()
    assert detail["status"] == "failed"
    assert "کارفرمای متصل" in detail["last_error"]
    assert not mock_adapter.sent


def test_scheduled_notification_can_be_cancelled(admin_client: TestClient, mock_adapter) -> None:
    project = _project_with_employer(admin_client)
    scheduled_at = (utcnow() + timedelta(days=1)).isoformat()
    create = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={"title": "یادآوری فردا", "body": "متن", "scheduled_at": scheduled_at},
    )
    assert create.status_code == 201, create.text
    assert create.json()["scheduled_at"] is not None

    cancel = admin_client.post(f"/api/v1/notifications/{create.json()['id']}/cancel")
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"
    run_worker(mock_adapter)
    assert not any("یادآوری فردا" in message["text"] for message in mock_adapter.sent)
    detail = admin_client.get(f"/api/v1/notifications/{create.json()['id']}").json()
    assert detail["status"] == "cancelled"


def test_send_now_overrides_schedule(admin_client: TestClient, mock_adapter) -> None:
    project = _project_with_employer(admin_client)
    create = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={
            "title": "ارسال فوری",
            "body": "متن",
            "scheduled_at": (utcnow() + timedelta(days=2)).isoformat(),
        },
    )
    send = admin_client.post(f"/api/v1/notifications/{create.json()['id']}/send")
    assert send.status_code == 200, send.text
    assert send.json()["scheduled_at"] is None
    run_worker(mock_adapter)
    detail = admin_client.get(f"/api/v1/notifications/{create.json()['id']}").json()
    assert detail["status"] == "sent"


def test_notification_history_pagination(admin_client: TestClient) -> None:
    project = create_project(admin_client)
    for index in range(3):
        admin_client.post(
            f"/api/v1/projects/{project['id']}/notifications",
            json={"title": f"اطلاعیه {index}", "body": "متن"},
        )
    history = admin_client.get("/api/v1/notifications", params={"page_size": 2})
    assert history.status_code == 200
    body = history.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["pages"] == 2
    assert body["items"][0]["project_name"] == project["name"]

    filtered = admin_client.get("/api/v1/notifications", params={"status": "queued"})
    assert filtered.json()["total"] == 3


def test_cannot_send_cancelled_or_sent_notification(admin_client: TestClient, mock_adapter) -> None:
    project = _project_with_employer(admin_client)
    create = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={"title": "اطلاعیه", "body": "متن"},
    )
    run_worker(mock_adapter)
    resend = admin_client.post(f"/api/v1/notifications/{create.json()['id']}/send")
    assert resend.status_code == 409
    cancel = admin_client.post(f"/api/v1/notifications/{create.json()['id']}/cancel")
    assert cancel.status_code == 409
