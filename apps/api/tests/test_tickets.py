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
