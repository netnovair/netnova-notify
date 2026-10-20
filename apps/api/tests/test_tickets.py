from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import (
    approve_first_member,
    create_project,
    last_message,
    run_worker,
    telegram_update,
)


def _project_with_employer(admin_client: TestClient, telegram_id: int = 910001) -> dict:
    project = create_project(admin_client)
    telegram_update(admin_client, telegram_id=telegram_id, text=project["license_code"])
    approve_first_member(admin_client, project["id"])
    return project


def _employer_member(admin_client: TestClient, project_id: str) -> dict:
    members = admin_client.get(f"/api/v1/projects/{project_id}/members").json()
    return next(item for item in members if item["status"] == "active")


def test_employer_files_ticket_from_bot_and_admin_replies(
    admin_client: TestClient, mock_adapter
) -> None:
    _project_with_employer(admin_client, 910002)

    # Employer starts the flow and provides subject + body.
    telegram_update(admin_client, telegram_id=910002, callback_data="0:newticket")
    assert "موضوع تیکت" in last_message(mock_adapter)["text"]
    telegram_update(admin_client, telegram_id=910002, text="قطعی گزارش مالی")
    assert "متن کامل تیکت" in last_message(mock_adapter)["text"]
    telegram_update(admin_client, telegram_id=910002, text="گزارش مالی دیروز باز نمی شود.")
    confirmation = last_message(mock_adapter)["text"]
    assert "تیکت شما ثبت شد" in confirmation

    listing = admin_client.get("/api/v1/tickets").json()
    assert listing["total"] == 1
    ticket = listing["items"][0]
    assert ticket["status"] == "pending_admin"
    assert ticket["admin_unread"] == 1
    assert ticket["subject"] == "قطعی گزارش مالی"

    detail = admin_client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert detail["admin_unread"] == 0
    assert detail["messages"][0]["author_type"] == "employer"
    assert detail["member_display_name"]

    reply = admin_client.post(
        f"/api/v1/tickets/{ticket['id']}/reply", json={"body": "بررسی شد، مشکل رفع شد."}
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["status"] == "pending_employer"

    # The employer receives a short alert with a button back to the ticket list.
    run_worker(mock_adapter)
    alert = last_message(mock_adapter)
    assert alert["chat_id"] == 910002
    assert "پاسخ جدید پشتیبانی" in alert["text"]
    buttons = alert["keyboard"]["inline_keyboard"]
    assert buttons[0][0]["callback_data"] == "0:tickets"

    # Closing and reopening by a new employer message is explicit.
    closed = admin_client.patch(f"/api/v1/tickets/{ticket['id']}/status", json={"status": "closed"})
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    telegram_update(admin_client, telegram_id=910002, callback_data="0:newticket")
    telegram_update(admin_client, telegram_id=910002, text="سوال دوم")
    telegram_update(admin_client, telegram_id=910002, text="لطفا دوباره بررسی کنید.")
    after = admin_client.get("/api/v1/tickets").json()["items"]
    assert after[0]["status"] == "pending_admin"


def test_employer_replies_to_existing_ticket_from_ticket_list(
    admin_client: TestClient, mock_adapter
) -> None:
    _project_with_employer(admin_client, 910003)
    telegram_update(admin_client, telegram_id=910003, callback_data="0:newticket")
    telegram_update(admin_client, telegram_id=910003, text="درخواست فاکتور")
    telegram_update(admin_client, telegram_id=910003, text="فاکتور مهر را می خواهم.")

    ticket = admin_client.get("/api/v1/tickets").json()["items"][0]
    admin_client.post(f"/api/v1/tickets/{ticket['id']}/reply", json={"body": "فاکتور ارسال شد."})

    telegram_update(admin_client, telegram_id=910003, callback_data="0:tickets")
    assert "درخواست فاکتور" in last_message(mock_adapter)["text"]
    telegram_update(admin_client, telegram_id=910003, callback_data="0:ticket:0")
    thread = last_message(mock_adapter)["text"]
    assert "فاکتور ارسال شد." in thread

    telegram_update(admin_client, telegram_id=910003, callback_data="0:treply:0")
    assert "پاسخ خود را" in last_message(mock_adapter)["text"]
    telegram_update(admin_client, telegram_id=910003, text="ممنون، دریافت شد.")
    assert "پاسخ شما ثبت شد" in last_message(mock_adapter)["text"]

    detail = admin_client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert detail["status"] == "pending_admin"
    assert detail["messages"][-1]["author_type"] == "employer"


def test_ticket_endpoints_require_admin_session(client: TestClient) -> None:
    assert client.get("/api/v1/tickets").status_code == 401
    assert client.get("/api/v1/admins").status_code == 401


def test_admin_can_open_ticket_for_project(admin_client: TestClient) -> None:
    project = create_project(admin_client)
    response = admin_client.post(
        "/api/v1/tickets",
        json={
            "project_id": project["id"],
            "subject": "پیگیری قرارداد",
            "body": "نسخه امضا شده را ارسال کنید.",
            "priority": "high",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created_by_type"] == "admin"
    assert body["status"] == "pending_employer"
    assert body["priority"] == "high"


# ---------------------------------------------------------------------------
# Image attachments
# ---------------------------------------------------------------------------
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x00\x00\x02\x00\x01\x54"
    b"\xa2O^\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_admin_can_attach_images_to_a_ticket(admin_client: TestClient) -> None:
    project = create_project(admin_client)
    ticket = admin_client.post(
        "/api/v1/tickets",
        json={
            "project_id": project["id"],
            "subject": "اسکرین شات مشکل",
            "body": "تصویر خطا را ببینید.",
        },
    ).json()

    upload = admin_client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        data={"body": "این هم تصویر خطا"},
        files=[("files", ("error-shot.png", PNG_BYTES, "image/png"))],
    )
    assert upload.status_code == 200, upload.text
    message = upload.json()["messages"][-1]
    assert message["author_type"] == "admin"
    assert message["body"] == "این هم تصویر خطا"
    assert len(message["attachments"]) == 1
    attachment = message["attachments"][0]
    assert attachment["content_type"] == "image/png"
    assert attachment["filename"] == "error-shot.png"
    assert attachment["size_bytes"] == len(PNG_BYTES)
    # The stored bytes are never inlined into the JSON payload.
    assert "data" not in attachment

    download = admin_client.get(f"/api/v1/tickets/attachments/{attachment['id']}")
    assert download.status_code == 200
    assert download.content == PNG_BYTES
    assert download.headers["content-type"] == "image/png"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in download.headers["cache-control"]

    # Anything that is not a raster image is rejected before it reaches the DB.
    rejected = admin_client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        files=[
            (
                "files",
                ("payload.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>', "image/svg+xml"),
            )
        ],
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "invalid_attachment"

    too_big = admin_client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        files=[
            (
                "files",
                ("huge.png", PNG_BYTES + b"0" * (5 * 1024 * 1024), "image/png"),
            )
        ],
    )
    assert too_big.status_code == 400
    assert too_big.json()["error"]["code"] == "invalid_attachment"

    # An image-only reply is allowed; the stored body explains the content.
    image_only = admin_client.post(
        f"/api/v1/tickets/{ticket['id']}/attachments",
        files=[("files", ("second.png", PNG_BYTES, "image/png"))],
    )
    assert image_only.status_code == 200, image_only.text
    assert image_only.json()["messages"][-1]["body"] == "تصویر پیوست"


def test_attachment_endpoint_requires_admin(client: TestClient) -> None:
    assert (
        client.get("/api/v1/tickets/attachments/00000000-0000-0000-0000-000000000000").status_code
        == 401
    )


def test_employer_sends_photo_in_ticket_conversation(
    admin_client: TestClient, mock_adapter
) -> None:
    _project_with_employer(admin_client, 910004)

    telegram_update(admin_client, telegram_id=910004, callback_data="0:newticket")
    telegram_update(admin_client, telegram_id=910004, text="خطای صفحه پرداخت")
    telegram_update(
        admin_client,
        telegram_id=910004,
        text="تصویر خطا را فرستادم.",
        photo=True,
    )
    assert "تیکت شما ثبت شد" in last_message(mock_adapter)["text"]
    # The largest size was requested, not the thumbnail.
    assert mock_adapter.downloads[-1]["file_id"] == "mock-photo-large"

    ticket = admin_client.get("/api/v1/tickets").json()["items"][0]
    detail = admin_client.get(f"/api/v1/tickets/{ticket['id']}").json()
    first = detail["messages"][0]
    assert first["channel"] == "telegram"
    assert first["body"] == "تصویر خطا را فرستادم."
    assert first["attachments"][0]["content_type"] == "image/png"

    # Replying with an image alone is accepted and keeps the thread moving.
    telegram_update(admin_client, telegram_id=910004, callback_data="0:treply:0")
    assert "پاسخ خود را" in last_message(mock_adapter)["text"]
    telegram_update(admin_client, telegram_id=910004, photo=True)
    assert "پاسخ شما ثبت شد" in last_message(mock_adapter)["text"]
    detail = admin_client.get(f"/api/v1/tickets/{ticket['id']}").json()
    assert detail["messages"][-1]["body"] == "تصویر پیوست"
    assert len(detail["messages"][-1]["attachments"]) == 1

    # Ticket images are forwarded to Telegram as real uploads when an alert is
    # sent; the test environment has no admin chat id, so the helper is checked
    # directly instead of through the worker's settings.
    from types import SimpleNamespace

    from app.adapters.telegram.mock import MockTelegramAdapter
    from app.worker.handlers import _forward_attachments

    media_adapter = MockTelegramAdapter()
    _forward_attachments(
        media_adapter,
        555,
        SimpleNamespace(
            attachments=[
                SimpleNamespace(
                    id="a1", data=PNG_BYTES, filename="shot.png", content_type="image/png"
                )
            ]
        ),
    )
    assert media_adapter.sent[-1]["chat_id"] == 555
    assert media_adapter.sent[-1]["media"]["filename"] == "shot.png"


def test_photo_without_ticket_conversation_is_explained(
    admin_client: TestClient, mock_adapter
) -> None:
    _project_with_employer(admin_client, 910005)
    telegram_update(admin_client, telegram_id=910005, photo=True)
    message = last_message(mock_adapter)["text"]
    assert "برای ارسال تصویر" in message


def test_admin_ticket_alert_links_back_to_the_panel(
    admin_client: TestClient, mock_adapter, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "admin_telegram_chat_id", 555002)
    _project_with_employer(admin_client, 910007)

    telegram_update(admin_client, telegram_id=910007, callback_data="0:newticket")
    telegram_update(admin_client, telegram_id=910007, text="سوال فنی")
    telegram_update(admin_client, telegram_id=910007, text="دسترسی پنل کار نمی کند.")

    run_worker(mock_adapter)
    alerts = [
        message
        for message in mock_adapter.sent
        if message["chat_id"] == 555002 and "تیکت جدید" in message["text"]
    ]
    assert alerts, [(m["chat_id"], m["text"][:40]) for m in mock_adapter.sent]
    buttons = alerts[-1]["keyboard"]["inline_keyboard"]
    assert buttons[0][0]["url"].endswith("/tickets")
    assert buttons[0][0]["text"] == "پاسخ در پنل"
