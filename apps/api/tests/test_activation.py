from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.license import License
from app.models.telegram import ProjectMember
from tests.helpers import (
    activate_employer,
    approve_first_member,
    auth_headers,
    create_project,
    last_message,
    run_worker,
    telegram_update,
)


def _expire_license(license_id: str) -> None:
    with SessionLocal() as db:
        db.execute(
            update(License)
            .where(License.id == license_id)
            .values(expires_at=utcnow() - timedelta(minutes=1))
        )
        db.commit()


def test_invalid_license_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/licenses/activate",
        json={"code": "NN-AAAA-BBBB-CCCC-DDDD", "telegram_id": 900001},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_license"


def test_activation_requires_bot_secret(client: TestClient) -> None:
    response = client.post(
        "/api/v1/licenses/activate",
        json={"code": "NN-AAAA-BBBB-CCCC-DDDD", "telegram_id": 900001},
    )
    assert response.status_code == 403


def test_activation_flow_requires_admin_approval(admin_client: TestClient, mock_adapter) -> None:
    project = create_project(admin_client)
    code = project["license_code"]
    telegram_id = 700001
    activate_employer(client=admin_client, code=code, telegram_id=telegram_id)

    # Pending: the bot explicitly says the request is waiting for approval.
    telegram_update(admin_client, telegram_id=telegram_id, text="/start")
    assert "در انتظار تایید مدیر" in last_message(mock_adapter)["text"]

    members = admin_client.get(f"/api/v1/projects/{project['id']}/members").json()
    assert len(members) == 1
    assert members[0]["status"] == "pending_approval"

    approve_first_member(admin_client, project["id"])
    run_worker(mock_adapter)
    assert any("تایید شد" in message["text"] for message in mock_adapter.sent)

    telegram_update(admin_client, telegram_id=telegram_id, text="/start")
    menu = last_message(mock_adapter)
    assert project["name"] in menu["text"]
    callbacks = [
        button["callback_data"] for row in menu["keyboard"]["inline_keyboard"] for button in row
    ]
    assert "0:ann" in callbacks
    assert "0:fin" in callbacks
    assert "0:soon:performance" in callbacks

    with SessionLocal() as db:
        member = db.scalar(select(ProjectMember).where(ProjectMember.project_id == project["id"]))
        assert member is not None
        assert member.status == "active"
        license_row = db.scalar(select(License).where(License.project_id == project["id"]))
        assert license_row is not None
        assert license_row.status == "active"
        assert license_row.activated_at is not None


def test_license_cannot_be_used_by_second_employer(admin_client: TestClient, mock_adapter) -> None:
    project = create_project(admin_client)
    activate_employer(client=admin_client, code=project["license_code"], telegram_id=700010)
    second = admin_client.post(
        "/api/v1/licenses/activate",
        json={"code": project["license_code"], "telegram_id": 700011, "first_name": "دوم"},
        headers=auth_headers(),
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "license_in_use"


def test_revoked_license_is_rejected(admin_client: TestClient) -> None:
    project = create_project(admin_client)
    revoke = admin_client.post(
        f"/api/v1/licenses/{project['license']['id']}/revoke",
        json={"reason": "customer_request"},
    )
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["status"] == "revoked"
    response = admin_client.post(
        "/api/v1/licenses/activate",
        json={"code": project["license_code"], "telegram_id": 700020},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "license_revoked"


def test_expired_license_is_rejected(admin_client: TestClient) -> None:
    project = create_project(admin_client)
    _expire_license(project["license"]["id"])
    response = admin_client.post(
        "/api/v1/licenses/activate",
        json={"code": project["license_code"], "telegram_id": 700030},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "license_expired"
    listing = admin_client.get(f"/api/v1/projects/{project['id']}/licenses").json()
    assert listing[0]["effective_status"] == "expired"


def test_inactive_project_blocks_activation(admin_client: TestClient) -> None:
    project = create_project(admin_client)
    admin_client.patch(f"/api/v1/projects/{project['id']}", json={"status": "inactive"})
    response = admin_client.post(
        "/api/v1/licenses/activate",
        json={"code": project["license_code"], "telegram_id": 700040},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "project_inactive"


def test_reissue_rebinds_existing_employer(admin_client: TestClient, mock_adapter) -> None:
    project = create_project(admin_client)
    telegram_id = 700050
    activate_employer(client=admin_client, code=project["license_code"], telegram_id=telegram_id)
    approve_first_member(admin_client, project["id"])

    reissue = admin_client.post(f"/api/v1/projects/{project['id']}/licenses", json={})
    assert reissue.status_code == 201, reissue.text
    new_code = reissue.json()["code"]
    assert new_code != project["license_code"]

    # The old code stops working, but the approved employer keeps access.
    old_code = admin_client.post(
        "/api/v1/licenses/activate",
        json={"code": project["license_code"], "telegram_id": 700051},
        headers=auth_headers(),
    )
    assert old_code.status_code == 400
    telegram_update(admin_client, telegram_id=telegram_id, text="/start")
    assert project["name"] in last_message(mock_adapter)["text"]

    with SessionLocal() as db:
        member = db.scalar(select(ProjectMember).where(ProjectMember.project_id == project["id"]))
        license_row = db.scalar(
            select(License)
            .where(License.project_id == project["id"], License.status == "pending")
            .order_by(License.created_at.desc())
        )
        assert member is not None and license_row is not None
        assert member.license_id == license_row.id
        assert member.status == "active"


def test_revoked_license_revokes_member_access(admin_client: TestClient, mock_adapter) -> None:
    project = create_project(admin_client)
    telegram_id = 700060
    activate_employer(client=admin_client, code=project["license_code"], telegram_id=telegram_id)
    approve_first_member(admin_client, project["id"])

    revoke = admin_client.post(
        f"/api/v1/licenses/{project['license']['id']}/revoke",
        json={"reason": "fraud_suspected"},
    )
    assert revoke.status_code == 200
    telegram_update(admin_client, telegram_id=telegram_id, text="/start")
    text = last_message(mock_adapter)["text"]
    assert project["name"] not in text
    assert "کد لایسنس" in text

    with SessionLocal() as db:
        member = db.scalar(select(ProjectMember).where(ProjectMember.project_id == project["id"]))
        assert member is not None
        assert member.status == "revoked"
