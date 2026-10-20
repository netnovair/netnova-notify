from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.security import utcnow
from tests.helpers import (
    activate_employer,
    approve_first_member,
    create_project,
    run_worker,
)


def test_dashboard_reports_real_counts(admin_client: TestClient, mock_adapter) -> None:
    first = create_project(admin_client, name="پروژه یک", slug="dash-one")
    second = create_project(admin_client, name="پروژه دو", slug="dash-two")

    activate_employer(client=admin_client, code=first["license_code"], telegram_id=840001)
    notification = admin_client.post(
        f"/api/v1/projects/{first['id']}/notifications",
        json={"title": "اطلاعیه", "body": "متن"},
    )
    assert notification.status_code == 201
    admin_client.post(
        f"/api/v1/projects/{second['id']}/payments",
        json={
            "title": "پرداخت باز",
            "amount_minor": 1_500_000,
            "currency": "IRT",
            "due_at": (utcnow() + timedelta(days=5)).isoformat(),
        },
    )

    summary = admin_client.get("/api/v1/dashboard")
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["projects_total"] == 2
    assert body["projects_active"] == 2
    assert body["notifications_total"] == 1
    assert body["queued_notifications"] == 1
    assert body["failed_notifications"] == 0
    assert body["open_payments"] == 1
    assert body["open_payments_amount_by_currency"] == {"IRT": 1_500_000}
    assert body["pending_members"] == 1
    assert body["license_attention"] == 0
    actions = [item["action"] for item in body["recent_activity"]]
    assert "project.created" in actions
    assert "payment.created" in actions
    assert all(item["action_label"] for item in body["recent_activity"])

    approve_first_member(admin_client, first["id"])
    run_worker(mock_adapter)
    after = admin_client.get("/api/v1/dashboard").json()
    assert after["queued_notifications"] == 0
    assert after["pending_members"] == 0

    admin_client.patch(f"/api/v1/projects/{second['id']}", json={"status": "inactive"})
    inactive = admin_client.get("/api/v1/dashboard").json()
    assert inactive["projects_active"] == 1
    assert inactive["projects_total"] == 2


def test_dashboard_is_empty_but_real(admin_client: TestClient) -> None:
    body = admin_client.get("/api/v1/dashboard").json()
    assert body["projects_total"] == 0
    assert body["notifications_total"] == 0
    assert body["open_payments"] == 0
    # Only the real bootstrap/login audit entries exist; no fabricated activity.
    actions = [item["action"] for item in body["recent_activity"]]
    assert "project.created" not in actions
    assert all(item["created_at"] for item in body["recent_activity"])


def test_system_status_hides_secrets(admin_client: TestClient) -> None:
    status = admin_client.get("/api/v1/system/status").json()
    assert status["telegram"]["bot_configured"] is False
    assert status["telegram"]["webhook_secret_configured"] is True
    assert "secret" not in str(status).lower().replace("webhook_secret_configured", "")
    assert status["worker"]["status"] in ("unknown", "offline", "online")
    assert status["https_required"] is False
    assert status["pending_jobs"] == 0
