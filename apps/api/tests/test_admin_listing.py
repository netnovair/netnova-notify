from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.license import License
from tests.helpers import activate_employer, approve_first_member, create_project


def _project_with_employer(client: TestClient, name: str, telegram_id: int) -> dict:
    project = create_project(client, name=name)
    activate_employer(client=client, code=project["license_code"], telegram_id=telegram_id)
    approve_first_member(client, project["id"])
    return project


def test_license_list_requires_admin_session(client: TestClient) -> None:
    assert client.get("/api/v1/licenses").status_code == 401


def test_license_list_includes_project_name_and_filters(
    admin_client: TestClient,
) -> None:
    first = _project_with_employer(admin_client, name="پروژه آلفا", telegram_id=920001)
    second = create_project(admin_client, name="پروژه بتا")

    listing = admin_client.get("/api/v1/licenses")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 2
    assert {item["project_id"] for item in body["items"]} == {first["id"], second["id"]}
    names = {item["project_name"] for item in body["items"]}
    assert names == {"پروژه آلفا", "پروژه بتا"}
    # Raw license codes are never serialized in listings.
    assert first["license_code"] not in listing.text

    active = admin_client.get("/api/v1/licenses", params={"status": "active"})
    assert active.status_code == 200
    assert active.json()["total"] == 1
    assert active.json()["items"][0]["project_name"] == "پروژه آلفا"

    pending = admin_client.get("/api/v1/licenses", params={"status": "pending"})
    assert pending.json()["total"] == 1
    assert pending.json()["items"][0]["project_name"] == "پروژه بتا"

    revoked = admin_client.get("/api/v1/licenses", params={"status": "revoked"})
    assert revoked.json()["total"] == 0
    assert revoked.json()["items"] == []


def test_license_list_reports_expired_licenses(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه منقضی")
    license_id = project["license"]["id"]
    with SessionLocal() as db:
        db.execute(
            update(License)
            .where(License.id == license_id)
            .values(expires_at=utcnow() - timedelta(minutes=5))
        )
        db.commit()

    listing = admin_client.get("/api/v1/licenses", params={"status": "expired"})
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == license_id
    assert body["items"][0]["project_name"] == "پروژه منقضی"
    assert body["items"][0]["effective_status"] == "expired"


def test_payment_list_requires_admin_session(client: TestClient) -> None:
    assert client.get("/api/v1/payments").status_code == 401


def test_payment_list_scopes_by_project_and_status(admin_client: TestClient) -> None:
    first = create_project(admin_client, name="پروژه مالی یک")
    second = create_project(admin_client, name="پروژه مالی دو")

    def create(project_id: str, title: str, amount: int) -> dict:
        response = admin_client.post(
            f"/api/v1/projects/{project_id}/payments",
            json={
                "title": title,
                "amount_minor": amount,
                "currency": "IRT",
                "due_at": (utcnow() + timedelta(days=7)).isoformat(),
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    open_payment = create(first["id"], "پرداخت باز", 1_000_000)
    paid_payment = create(first["id"], "پرداخت تسویه", 2_000_000)
    create(second["id"], "پرداخت پروژه دوم", 3_000_000)
    mark = admin_client.post(f"/api/v1/payments/{paid_payment['id']}/mark-paid")
    assert mark.status_code == 200, mark.text

    everything = admin_client.get("/api/v1/payments")
    assert everything.status_code == 200
    assert everything.json()["total"] == 3
    assert {item["project_name"] for item in everything.json()["items"]} == {
        "پروژه مالی یک",
        "پروژه مالی دو",
    }

    scoped = admin_client.get("/api/v1/payments", params={"project_id": first["id"]})
    assert scoped.json()["total"] == 2

    unpaid = admin_client.get("/api/v1/payments", params={"status": "unpaid"})
    assert unpaid.json()["total"] == 2
    assert all(item["status"] == "unpaid" for item in unpaid.json()["items"])
    assert all(item["is_overdue"] is False for item in unpaid.json()["items"])

    paid = admin_client.get("/api/v1/payments", params={"status": "paid"})
    assert paid.json()["total"] == 1
    assert paid.json()["items"][0]["id"] == paid_payment["id"]

    # Open payments expose their next scheduled reminder.
    item = next(entry for entry in unpaid.json()["items"] if entry["id"] == open_payment["id"])
    assert item["next_reminder_at"] is not None
    assert item["amount_minor"] == 1_000_000
