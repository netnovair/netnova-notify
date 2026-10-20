from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import approve_first_member, create_project, telegram_update


def _active_member(admin_client: TestClient, telegram_id: int = 940001) -> tuple[dict, dict]:
    project = create_project(admin_client)
    telegram_update(admin_client, telegram_id=telegram_id, text=project["license_code"])
    member = approve_first_member(admin_client, project["id"])
    return project, member


def test_admin_registers_provider_destinations(admin_client: TestClient) -> None:
    project, member = _active_member(admin_client)

    sms = admin_client.put(
        f"/api/v1/projects/{project['id']}/members/{member['id']}/channels/smsir",
        json={"external_id": "0912 123 4567", "label": "موبایل مدیر"},
    )
    assert sms.status_code == 200, sms.text
    assert sms.json()["external_id"] == "09121234567"

    bale = admin_client.put(
        f"/api/v1/projects/{project['id']}/members/{member['id']}/channels/bale",
        json={"external_id": "123456789"},
    )
    assert bale.status_code == 200, bale.text

    listed = admin_client.get(
        f"/api/v1/projects/{project['id']}/members/{member['id']}/channels"
    ).json()
    assert {row["channel"] for row in listed} == {"smsir", "bale"}

    # The member listing embeds the destinations so the panel shows them inline.
    members = admin_client.get(f"/api/v1/projects/{project['id']}/members").json()
    identities = {row["channel"]: row["external_id"] for row in members[0]["channel_identities"]}
    assert identities["smsir"] == "09121234567"

    removed = admin_client.delete(
        f"/api/v1/projects/{project['id']}/members/{member['id']}/channels/bale"
    )
    assert removed.status_code == 204
    remaining = admin_client.get(
        f"/api/v1/projects/{project['id']}/members/{member['id']}/channels"
    ).json()
    assert [row["channel"] for row in remaining] == ["smsir"]


def test_invalid_destinations_are_rejected(admin_client: TestClient) -> None:
    project, member = _active_member(admin_client, 940002)
    bad_phone = admin_client.put(
        f"/api/v1/projects/{project['id']}/members/{member['id']}/channels/smsir",
        json={"external_id": "12345"},
    )
    assert bad_phone.status_code == 409

    telegram = admin_client.put(
        f"/api/v1/projects/{project['id']}/members/{member['id']}/channels/telegram",
        json={"external_id": "123456"},
    )
    assert telegram.status_code == 404

    unknown = admin_client.put(
        f"/api/v1/projects/{project['id']}/members/{member['id']}/channels/whatsapp",
        json={"external_id": "123456"},
    )
    assert unknown.status_code == 404


def test_duplicate_destination_cannot_span_two_projects(admin_client: TestClient) -> None:
    first_project, first = _active_member(admin_client, 940003)
    second_project, second = _active_member(admin_client, 940004)

    first_url = (
        f"/api/v1/projects/{first_project['id']}/members/{first['id']}/channels/smsir"
    )
    assert admin_client.put(first_url, json={"external_id": "09121112233"}).status_code == 200
    duplicate = admin_client.put(
        f"/api/v1/projects/{second_project['id']}/members/{second['id']}/channels/smsir",
        json={"external_id": "09121112233"},
    )
    assert duplicate.status_code == 409
