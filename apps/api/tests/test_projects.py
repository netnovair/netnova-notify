from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.license import License
from tests.helpers import activate_employer, approve_first_member, create_project


def test_create_project_issues_license_and_hides_raw_code(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="فروشگاه آرمان", client_name="آرمان")
    assert project["license_code"].startswith("NN-")
    assert project["license"]["status"] == "pending"
    assert project["license"]["code_prefix"] == project["license_code"][:5]
    assert "code" not in project["license"]
    assert len(project["features"]) == 6
    assert project["is_demo"] is False

    with SessionLocal() as db:
        license_row = db.scalar(select(License).where(License.project_id == project["id"]))
        assert license_row is not None
        assert license_row.code_hash != project["license_code"]
        assert project["license_code"] not in license_row.code_hash
        assert len(license_row.code_hash) == 64

    detail = admin_client.get(f"/api/v1/projects/{project['id']}")
    assert detail.status_code == 200
    serialized = detail.text
    assert project["license_code"] not in serialized
    assert detail.json()["license"]["code_prefix"] == project["license_code"][:5]


def test_list_search_and_filter(admin_client: TestClient) -> None:
    create_project(admin_client, name="پروژه الف", client_name="کارفرمای الف", slug="alpha")
    create_project(admin_client, name="پروژه ب", client_name="کارفرمای ب", slug="beta")
    listing = admin_client.get("/api/v1/projects")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["pages"] == 1
    assert body["items"][0]["license_status"] == "pending"
    assert body["items"][0]["enabled_features"]

    search = admin_client.get("/api/v1/projects", params={"search": "alpha"})
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["slug"] == "alpha"


def test_duplicate_slug_conflict(admin_client: TestClient) -> None:
    create_project(admin_client, slug="same-slug")
    response = admin_client.post(
        "/api/v1/projects",
        json={"name": "پروژه دیگر", "client_name": "کارفرما", "slug": "same-slug"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "slug_taken"


def test_update_project_and_features(admin_client: TestClient) -> None:
    project = create_project(admin_client)
    response = admin_client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "name": "نام تازه",
            "features": {"performance": False, "financial": True},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "نام تازه"
    features = {item["key"]: item["enabled"] for item in body["features"]}
    assert features["performance"] is False
    assert features["financial"] is True

    invalid = admin_client.patch(
        f"/api/v1/projects/{project['id']}", json={"features": {"unknown": True}}
    )
    assert invalid.status_code == 422


def test_deactivate_project_cancels_queued_notification(admin_client: TestClient) -> None:
    project = create_project(admin_client)
    notification = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={
            "title": "اطلاعیه زمان بندی شده",
            "body": "متن",
            "scheduled_at": "2030-01-01T10:00:00Z",
        },
    )
    assert notification.status_code == 201, notification.text
    assert notification.json()["status"] == "queued"

    response = admin_client.patch(f"/api/v1/projects/{project['id']}", json={"status": "inactive"})
    assert response.status_code == 200
    assert response.json()["status"] == "inactive"
    detail = admin_client.get(f"/api/v1/notifications/{notification.json()['id']}")
    assert detail.json()["status"] == "cancelled"

    blocked = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={"title": "پس از غیرفعال سازی", "body": "متن"},
    )
    assert blocked.status_code == 409


def test_unknown_project_returns_404(admin_client: TestClient) -> None:
    missing = "00000000-0000-4000-8000-000000000000"
    assert admin_client.get(f"/api/v1/projects/{missing}").status_code == 404
    assert admin_client.get("/api/v1/projects/not-a-uuid").status_code == 422


def test_member_operations_are_scoped_to_the_project(admin_client: TestClient) -> None:
    first = create_project(admin_client, name="پروژه اول", slug="scope-one")
    second = create_project(admin_client, name="پروژه دوم", slug="scope-two")
    activate_employer(admin_client, code=first["license_code"], telegram_id=930001)
    member = approve_first_member(admin_client, first["id"])

    # The member id is valid, but not under the second project.
    response = admin_client.post(f"/api/v1/projects/{second['id']}/members/{member['id']}/revoke")
    assert response.status_code == 404
    # The member itself is untouched.
    members = admin_client.get(f"/api/v1/projects/{first['id']}/members").json()
    assert members[0]["status"] == "active"


def test_unknown_project_license_operations_return_404(admin_client: TestClient) -> None:
    missing = uuid.uuid4()
    assert admin_client.get(f"/api/v1/projects/{missing}/licenses").status_code == 404
    assert admin_client.post(f"/api/v1/projects/{missing}/licenses", json={}).status_code == 404
