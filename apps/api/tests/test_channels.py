from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.messaging.base import (
    ChannelNotConfigured,
    DeliveryResult,
    PermanentChannelError,
)
from app.adapters.messaging.providers import SmsIrAdapter
from app.adapters.messaging.registry import CHANNELS, channel_catalog
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.notification import Notification
from app.models.project import ProjectChannel
from app.models.ticket import MemberChannelIdentity
from app.services.notifications import NotificationService
from tests.helpers import approve_first_member, create_project, telegram_update

settings = get_settings()


def _project_with_employer(admin_client: TestClient, telegram_id: int = 920001) -> dict:
    project = create_project(admin_client)
    telegram_update(admin_client, telegram_id=telegram_id, text=project["license_code"])
    approve_first_member(admin_client, project["id"])
    return project


def _add_sms_identity(project_id: str, member_id: str, phone: str = "09121234567") -> None:
    with SessionLocal() as db:
        db.add(
            MemberChannelIdentity(
                project_id=uuid.UUID(project_id),
                project_member_id=uuid.UUID(member_id),
                channel="smsir",
                external_id=phone,
            )
        )
        # The service refuses enabling an unconfigured provider; tests insert the
        # enablement row directly because the delivery path is what is under test.
        channel = db.scalar(
            select(ProjectChannel).where(
                ProjectChannel.project_id == uuid.UUID(project_id),
                ProjectChannel.channel == "smsir",
            )
        )
        assert channel is not None
        channel.enabled = True
        db.commit()


class _FakeChannel:
    def __init__(self, channel: str, error: Exception | None = None) -> None:
        self.channel = channel
        self.error = error
        self.sent: list[tuple[str, str]] = []

    @property
    def configured(self) -> bool:
        return True

    @property
    def mode(self) -> str:
        return "http"

    def send(self, recipient: str, text: str, keyboard: dict | None = None) -> DeliveryResult:
        if self.error:
            raise self.error
        self.sent.append((recipient, text))
        return DeliveryResult(message_id="fake-1")

    def send_plain(self, recipient: str, text: str) -> DeliveryResult:
        return self.send(recipient, text, None)


def _enable_smsir(admin_client: TestClient, project: dict) -> None:
    # The channel is unconfigured in tests, so the API refuses to enable it.
    # Enablement is set directly here to exercise the delivery path itself.
    member_id = admin_client.get(f"/api/v1/projects/{project['id']}/members").json()[0]["id"]
    _add_sms_identity(project["id"], member_id)


def test_channel_catalog_is_honest(admin_client: TestClient) -> None:
    catalog = admin_client.get("/api/v1/channels").json()
    keys = {item["key"] for item in catalog}
    assert keys == {"telegram", "bale", "eitaa", "smsir"}
    telegram = next(item for item in catalog if item["key"] == "telegram")
    assert telegram["configured"] is True
    assert telegram["mode"] == "mock"
    for key in ("bale", "eitaa", "smsir"):
        item = next(entry for entry in catalog if entry["key"] == key)
        # No credentials in the test environment: never claim they are ready.
        assert item["configured"] is False
        assert item["mode"] == "unconfigured"
        assert item["beta"] is True


def test_enabling_unconfigured_channel_is_refused(admin_client: TestClient) -> None:
    project = create_project(admin_client)
    response = admin_client.put(
        f"/api/v1/projects/{project['id']}/channels/smsir", json={"enabled": True}
    )
    assert response.status_code == 409
    unknown = admin_client.put(
        f"/api/v1/projects/{project['id']}/channels/whatsapp", json={"enabled": True}
    )
    assert unknown.status_code == 404


def test_notification_rejects_channels_disabled_for_the_project(admin_client: TestClient) -> None:
    project = _project_with_employer(admin_client)
    response = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={
            "type": "announcement",
            "title": "اطلاعیه",
            "body": "متن اطلاعیه تست",
            "channels": ["smsir"],
        },
    )
    assert response.status_code == 409


def test_feature_catalog_drives_project_toggles(admin_client: TestClient) -> None:
    catalog = admin_client.get("/api/v1/features").json()
    keys = [item["key"] for item in catalog]
    assert keys == [
        "announcements",
        "financial",
        "support",
        "advisor",
        "performance",
        "progress",
    ]

    project = create_project(admin_client)
    detail = admin_client.get(f"/api/v1/projects/{project['id']}").json()
    assert {item["key"] for item in detail["features"]} == set(keys)
    channels = {item["channel"]: item for item in detail["channels"]}
    assert channels["telegram"]["enabled"] is True
    assert channels["bale"]["enabled"] is False

    unknown = admin_client.put(
        f"/api/v1/projects/{project['id']}/features",
        json={"features": {"financial": False, "invoice": True}},
    )
    assert unknown.status_code == 422

    updated = admin_client.put(
        f"/api/v1/projects/{project['id']}/features",
        json={"features": {"financial": False}},
    )
    assert updated.status_code == 200, updated.text
    flags = {item["key"]: item["enabled"] for item in updated.json()["features"]}
    assert flags["financial"] is False
    assert flags["announcements"] is True


def test_sms_dispatch_uses_member_identity(admin_client: TestClient, monkeypatch) -> None:
    project = _project_with_employer(admin_client, 920002)
    _enable_smsir(admin_client, project)

    fake_sms = _FakeChannel("smsir")
    monkeypatch.setattr(
        "app.services.notifications.get_channel_adapter",
        lambda channel, _settings=None: fake_sms,
    )

    from app.adapters.telegram.mock import MockTelegramAdapter

    telegram = MockTelegramAdapter()
    create = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={
            "type": "announcement",
            "title": "پرداخت جدید",
            "body": "لطفا مبلغ را بررسی کنید.",
            "channels": ["telegram", "smsir"],
        },
    )
    assert create.status_code == 201, create.text
    notification_id = create.json()["id"]

    with SessionLocal() as db:
        notification = db.get(Notification, uuid.UUID(notification_id))
        NotificationService.deliver(db, notification=notification, adapter=telegram)
        db.commit()
        db.expire_all()
        refreshed = db.get(Notification, uuid.UUID(notification_id))
        assert refreshed.status == "sent"
        assert {attempt.channel for attempt in refreshed.deliveries} == {"telegram", "smsir"}
    assert fake_sms.sent and fake_sms.sent[0][0] == "09121234567"
    # The SMS body is plain text; HTML tags from the Telegram formatting are gone.
    assert "<b>" not in fake_sms.sent[0][1]


def test_permanent_channel_error_fails_without_retry(admin_client: TestClient, monkeypatch) -> None:
    project = _project_with_employer(admin_client, 920004)
    _enable_smsir(admin_client, project)
    fake_sms = _FakeChannel("smsir", PermanentChannelError("invalid mobile"))
    monkeypatch.setattr(
        "app.services.notifications.get_channel_adapter",
        lambda channel, _settings=None: fake_sms,
    )

    create = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={
            "type": "announcement",
            "title": "تست خطا",
            "body": "متن تست خطا",
            "channels": ["smsir"],
        },
    )
    notification_id = create.json()["id"]

    from app.adapters.telegram.mock import MockTelegramAdapter

    with SessionLocal() as db:
        notification = db.get(Notification, uuid.UUID(notification_id))
        NotificationService.deliver(db, notification=notification, adapter=MockTelegramAdapter())
        db.commit()
        db.expire_all()
        refreshed = db.get(Notification, uuid.UUID(notification_id))
        assert refreshed.status == "failed"
        assert refreshed.deliveries[0].status == "failed"
        assert "invalid mobile" in (refreshed.last_error or "")


def test_smsir_rejects_keyboard_and_bad_numbers() -> None:
    adapter = SmsIrAdapter(settings)
    # The adapter is not configured in tests, so it must refuse honestly.
    with pytest.raises(ChannelNotConfigured):
        adapter.send_plain("09121234567", "سلام")
    with pytest.raises(PermanentChannelError):
        adapter.send("09121234567", "سلام", {"inline_keyboard": []})


def test_registry_unknown_channel() -> None:
    from app.adapters.messaging.registry import get_channel_adapter

    with pytest.raises(ChannelNotConfigured):
        get_channel_adapter("carrier-pigeon")
    assert set(CHANNELS) == {"telegram", "bale", "eitaa", "smsir"}
    assert len(channel_catalog()) == 4


def test_plain_text_strips_html() -> None:
    from app.adapters.messaging.providers import plain_text

    assert plain_text("<b>سلام</b><br/>دنیا") == "سلام\nدنیا"
    assert plain_text("a &lt; b") == "a < b"
