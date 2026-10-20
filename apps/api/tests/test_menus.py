from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.security import utcnow
from tests.helpers import (
    activate_employer,
    approve_first_member,
    create_project,
    last_message,
    run_worker,
    telegram_update,
)


def _employer(admin_client: TestClient, telegram_id: int, name: str = "پروژه منو") -> dict:
    project = create_project(admin_client, name=name)
    activate_employer(client=admin_client, code=project["license_code"], telegram_id=telegram_id)
    approve_first_member(admin_client, project["id"])
    return project


def test_announcements_menu_shows_real_notifications(
    admin_client: TestClient, mock_adapter
) -> None:
    project = _employer(admin_client, 850001)
    create = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={"title": "اطلاعیه مهم", "body": "متن کامل اطلاعیه"},
    )
    run_worker(mock_adapter)
    assert create.status_code == 201
    telegram_update(admin_client, telegram_id=850001, callback_data="0:ann")
    message = last_message(mock_adapter)
    assert "اطلاعیه مهم" in message["text"]
    assert "متن کامل اطلاعیه" in message["text"]
    callbacks = [
        button["callback_data"] for row in message["keyboard"]["inline_keyboard"] for button in row
    ]
    assert callbacks == ["0:home"]


def test_announcements_empty_state(admin_client: TestClient, mock_adapter) -> None:
    _employer(admin_client, 850002)
    telegram_update(admin_client, telegram_id=850002, callback_data="0:ann")
    assert "هنوز اطلاعیه ای ارسال نشده است" in last_message(mock_adapter)["text"]


def test_financial_menu_shows_open_payments(admin_client: TestClient, mock_adapter) -> None:
    project = _employer(admin_client, 850003)
    payment = admin_client.post(
        f"/api/v1/projects/{project['id']}/payments",
        json={
            "title": "پرداخت طراحی",
            "amount_minor": 3_200_000,
            "currency": "IRT",
            "due_at": (utcnow() + timedelta(days=4)).isoformat(),
        },
    )
    assert payment.status_code == 201, payment.text
    telegram_update(admin_client, telegram_id=850003, callback_data="0:fin")
    text = last_message(mock_adapter)["text"]
    # The financial menu is a balance summary, not a list of raw invoices.
    assert "وضعیت مالی" in text
    assert "بدهی" in text
    assert "3,200,000 تومان" in text
    assert "مانده حساب" in text
    buttons = [
        button["text"]
        for row in last_message(mock_adapter)["keyboard"]["inline_keyboard"]
        for button in row
    ]
    assert "ارسال رسید" in buttons
    assert "سوابق واریز" in buttons

    # The invoice list stays available behind its own button.
    telegram_update(admin_client, telegram_id=850003, callback_data="0:rinv")
    text = last_message(mock_adapter)["text"]
    assert "پرداخت طراحی" in text
    assert "3,200,000 تومان" in text


def test_financial_empty_state(admin_client: TestClient, mock_adapter) -> None:
    _employer(admin_client, 850004)
    telegram_update(admin_client, telegram_id=850004, callback_data="0:fin")
    text = last_message(mock_adapter)["text"]
    assert "هنوز فاکتوری ثبت نشده است" in text
    # No invoice at all must not be reported as a settled balance.
    assert "تسویه" not in text


def test_coming_soon_features_are_explicit(admin_client: TestClient, mock_adapter) -> None:
    _employer(admin_client, 850005)
    for feature, label in (
        ("performance", "گزارش عملکرد"),
        ("progress", "پیشرفت پروژه"),
    ):
        telegram_update(admin_client, telegram_id=850005, callback_data=f"0:soon:{feature}")
        text = last_message(mock_adapter)["text"]
        assert label in text
        assert "به زودی" in text


def test_support_menu_is_a_real_ticket_list(admin_client: TestClient, mock_adapter) -> None:
    _employer(admin_client, 850007)
    telegram_update(admin_client, telegram_id=850007, callback_data="0:tickets")
    text = last_message(mock_adapter)["text"]
    assert "هنوز تیکتی" in text
    buttons = last_message(mock_adapter)["keyboard"]["inline_keyboard"]
    assert any("ثبت تیکت جدید" in button[0]["text"] for button in buttons)


def test_help_and_home_callbacks(admin_client: TestClient, mock_adapter) -> None:
    _employer(admin_client, 850006)
    telegram_update(admin_client, telegram_id=850006, callback_data="help")
    assert "/menu" in last_message(mock_adapter)["text"]
    telegram_update(admin_client, telegram_id=850006, callback_data="0:home")
    assert "گزینه های زیر" in last_message(mock_adapter)["text"]


def test_multiple_projects_get_a_project_picker(admin_client: TestClient, mock_adapter) -> None:
    first = _employer(admin_client, 850007, name="پروژه اول")
    second = create_project(admin_client, name="پروژه دوم")
    activate_employer(client=admin_client, code=second["license_code"], telegram_id=850007)
    approve_first_member(admin_client, second["id"])

    telegram_update(admin_client, telegram_id=850007, text="/start")
    picker = last_message(mock_adapter)
    assert "پروژه های شما" in picker["text"]
    callbacks = [
        button["callback_data"] for row in picker["keyboard"]["inline_keyboard"] for button in row
    ]
    assert "p:0" in callbacks
    assert "p:1" in callbacks

    telegram_update(admin_client, telegram_id=850007, callback_data="p:0")
    assert first["name"] in last_message(mock_adapter)["text"]
    telegram_update(admin_client, telegram_id=850007, callback_data="p:1")
    assert second["name"] in last_message(mock_adapter)["text"]
