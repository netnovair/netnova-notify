from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.crypto import decrypt_code, encrypt_code
from app.core.security import hash_license_code, utcnow
from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.license import License
from tests.helpers import (
    activate_employer,
    approve_first_member,
    auth_headers,
    create_project,
    run_worker,
)


def test_codes_round_trip_through_aes_gcm() -> None:
    settings = get_settings()
    key = settings.license_encryption_key
    token = encrypt_code("NN-AAAA-BBBB", key=key)
    assert token != "NN-AAAA-BBBB"
    assert decrypt_code(token, key=key) == "NN-AAAA-BBBB"

    import pytest

    from app.core.crypto import LicenseCryptoError

    with pytest.raises(LicenseCryptoError):
        decrypt_code(token, key="another-key-entirely-1234567890")
    with pytest.raises(LicenseCryptoError):
        decrypt_code("not-base64!!", key=key)


def test_issued_license_is_decryptable_and_reveal_is_audited(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه کد")
    code = project["license_code"]
    license_id = project["license"]["id"] if "license" in project else None
    licenses = admin_client.get("/api/v1/licenses", params={"page_size": 5}).json()["items"]
    license_row = next(item for item in licenses if item["project_id"] == project["id"])
    assert license_id in (None, license_row["id"])

    revealed = admin_client.get(f"/api/v1/licenses/{license_row['id']}/code")
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["code"] == code
    assert revealed.json()["code_prefix"] == license_row["code_prefix"]

    # The list endpoint must keep exposing only the prefix.
    assert "code" not in license_row

    with SessionLocal() as db:
        row = db.scalar(select(License).where(License.id == uuid.UUID(license_row["id"])))
        assert row.code_encrypted
        assert code not in row.code_encrypted
        actions = [entry.action for entry in db.scalars(select(AuditLog)).all()]
        assert "license.code_viewed" in actions


def test_hash_only_license_requires_reissue(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه قدیمی")
    old_code = project["license_code"]

    # Simulate a license issued before encryption existed.
    with SessionLocal() as db:
        row = db.scalar(
            select(License).where(
                License.code_hash == hash_license_code(old_code, get_settings().secret_key)
            )
        )
        assert row is not None
        old_id = str(row.id)
        row.code_encrypted = None
        db.commit()

    reveal = admin_client.get(f"/api/v1/licenses/{old_id}/code")
    assert reveal.status_code == 409
    assert reveal.json()["error"]["code"] == "license_code_unavailable"

    reissued = admin_client.post(f"/api/v1/licenses/{old_id}/reissue")
    assert reissued.status_code == 201, reissued.text
    new_code = reissued.json()["code"]
    assert new_code != old_code

    # The old code stops working immediately; the new one is usable.
    stale = admin_client.post(
        "/api/v1/licenses/activate",
        json={"code": old_code, "telegram_id": 870001, "first_name": "کارفرما"},
        headers=auth_headers(),
    )
    assert stale.status_code in (400, 403, 404), stale.text
    fresh = admin_client.post(
        "/api/v1/licenses/activate",
        json={"code": new_code, "telegram_id": 870002, "first_name": "کارفرما"},
        headers=auth_headers(),
    )
    assert fresh.status_code == 200, fresh.text
    approve_first_member(admin_client, project["id"])

    shown = admin_client.get(f"/api/v1/licenses/{reissued.json()['id']}/code")
    assert shown.status_code == 200
    assert shown.json()["code"] == new_code


def test_license_is_delivered_privately_to_the_employer(
    admin_client: TestClient, mock_adapter
) -> None:
    project = create_project(admin_client, name="پروژه ارسال کد")
    code = project["license_code"]
    activate_employer(client=admin_client, code=code, telegram_id=870010)
    approve_first_member(admin_client, project["id"])

    licenses = admin_client.get("/api/v1/licenses", params={"page_size": 5}).json()["items"]
    license_row = next(item for item in licenses if item["project_id"] == project["id"])

    delivered = admin_client.post(f"/api/v1/licenses/{license_row['id']}/deliver", json={})
    assert delivered.status_code == 200, delivered.text

    run_worker(mock_adapter)
    messages = [message for message in mock_adapter.sent if code in message["text"]]
    assert messages, [message["text"] for message in mock_adapter.sent]
    # The code is sent in a private chat of the employer, never to a group.
    assert messages[-1]["chat_id"] == 870010
    assert "<code>" in messages[-1]["text"]


def test_reveal_is_rate_limited(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه محدودیت")
    licenses = admin_client.get("/api/v1/licenses", params={"page_size": 5}).json()["items"]
    license_row = next(item for item in licenses if item["project_id"] == project["id"])

    statuses = [
        admin_client.get(f"/api/v1/licenses/{license_row['id']}/code").status_code
        for _ in range(11)
    ]
    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429


def test_expired_or_missing_license_is_not_delivered(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه بدون کارفرما")
    licenses = admin_client.get("/api/v1/licenses", params={"page_size": 5}).json()["items"]
    license_row = next(item for item in licenses if item["project_id"] == project["id"])
    response = admin_client.post(f"/api/v1/licenses/{license_row['id']}/deliver", json={})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_used_license_row_still_shows_prefix_after_activation(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه پیشوند")
    activate_employer(client=admin_client, code=project["license_code"], telegram_id=870020)
    licenses = admin_client.get("/api/v1/licenses", params={"page_size": 5}).json()["items"]
    row = next(item for item in licenses if item["project_id"] == project["id"])
    assert row["code_prefix"]
    assert len(row["code_prefix"]) <= 8
    assert "code" not in row
    assert utcnow() is not None
