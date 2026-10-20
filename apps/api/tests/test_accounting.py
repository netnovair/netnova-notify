from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.accounting import PaymentReceipt
from app.models.payment import Payment
from tests.helpers import (
    activate_employer,
    approve_first_member,
    create_project,
    last_message,
    run_worker,
    telegram_update,
)


def _employer(admin_client: TestClient, telegram_id: int, name: str = "پروژه مالی") -> dict:
    project = create_project(admin_client, name=name)
    activate_employer(client=admin_client, code=project["license_code"], telegram_id=telegram_id)
    approve_first_member(admin_client, project["id"])
    return project


def _invoice(admin_client: TestClient, project_id: str, **overrides) -> dict:
    payload = {
        "title": "فاکتور طراحی",
        "amount_minor": 5_000_000,
        "currency": "IRT",
        "due_at": (utcnow() + timedelta(days=10)).isoformat(),
        "notes": "",
    }
    payload.update(overrides)
    response = admin_client.post(f"/api/v1/projects/{project_id}/payments", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _receipt(admin_client: TestClient, project_id: str, amount: int = 5_000_000) -> dict:
    response = admin_client.post(
        f"/api/v1/accounting/projects/{project_id}/receipts",
        json={"amount_minor": amount, "currency": "IRT", "note": "واریز بانکی"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _totals(admin_client: TestClient, project_id: str) -> dict:
    response = admin_client.get(f"/api/v1/accounting/projects/{project_id}/totals")
    assert response.status_code == 200, response.text
    return response.json()["totals"][0]


def test_payment_methods_are_scoped_and_audited(admin_client: TestClient) -> None:
    global_row = admin_client.post(
        "/api/v1/accounting/payment-methods",
        json={"title": "کارت اصلی", "card_number": "6037 9977 1122 3344", "bank_name": "ملی"},
    )
    assert global_row.status_code == 201, global_row.text
    assert global_row.json()["card_number"] == "6037997711223344"
    assert global_row.json()["project_id"] is None

    project = create_project(admin_client, name="پروژه کارت")
    other = create_project(admin_client, name="پروژه دیگر")
    scoped = admin_client.post(
        "/api/v1/accounting/payment-methods",
        json={
            "project_id": project["id"],
            "title": "کارت پروژه",
            "card_number": "5022291012345678",
        },
    )
    assert scoped.status_code == 201, scoped.text

    # A project sees its own card plus the global one, never another project's card.
    visible = admin_client.get(
        "/api/v1/accounting/payment-methods", params={"project_id": project["id"]}
    ).json()
    assert {row["title"] for row in visible} == {"کارت اصلی", "کارت پروژه"}
    foreign = admin_client.get(
        "/api/v1/accounting/payment-methods", params={"project_id": other["id"]}
    ).json()
    assert [row["title"] for row in foreign] == ["کارت اصلی"]

    # The bot shows the project card first and never another project's number.
    from app.services.accounting import PaymentMethodService

    with SessionLocal() as db:
        import uuid

        rows = PaymentMethodService.for_project(db, uuid.UUID(project["id"]))
        assert [row.title for row in rows] == ["کارت پروژه"]
        rows = PaymentMethodService.for_project(db, uuid.UUID(other["id"]))
        assert [row.title for row in rows] == ["کارت اصلی"]

    bad = admin_client.post(
        "/api/v1/accounting/payment-methods",
        json={"title": "نامعتبر", "card_number": "1234abcd"},
    )
    assert bad.status_code == 422

    deleted = admin_client.delete(f"/api/v1/accounting/payment-methods/{scoped.json()['id']}")
    assert deleted.status_code == 204
    remaining = admin_client.get(
        "/api/v1/accounting/payment-methods", params={"project_id": project["id"]}
    ).json()
    assert [row["title"] for row in remaining] == ["کارت اصلی"]


def test_receipt_approval_allocates_oldest_due_first(admin_client: TestClient) -> None:
    project = _employer(admin_client, 860001)
    later = _invoice(
        admin_client,
        project["id"],
        title="فاکتور دوم",
        amount_minor=3_000_000,
        due_at=(utcnow() + timedelta(days=30)).isoformat(),
    )
    sooner = _invoice(
        admin_client,
        project["id"],
        title="فاکتور اول",
        amount_minor=2_000_000,
        due_at=(utcnow() + timedelta(days=5)).isoformat(),
    )
    totals = _totals(admin_client, project["id"])
    assert totals["debt_minor"] == 5_000_000
    assert totals["settled"] is False

    receipt = _receipt(admin_client, project["id"], amount=4_000_000)
    assert receipt["status"] == "pending"
    pending = _totals(admin_client, project["id"])
    assert pending["pending_receipts"] == 1
    assert pending["debt_minor"] == 5_000_000

    approved = admin_client.post(f"/api/v1/accounting/receipts/{receipt['id']}/approve")
    assert approved.status_code == 200, approved.text
    allocations = {row["payment_id"]: row["amount_minor"] for row in approved.json()["allocations"]}
    assert allocations == {sooner["id"]: 2_000_000, later["id"]: 2_000_000}

    after = _totals(admin_client, project["id"])
    assert after["debt_minor"] == 1_000_000
    assert after["paid_minor"] == 4_000_000
    assert after["credit_minor"] == 0

    with SessionLocal() as db:
        import uuid

        sooner_row = db.get(Payment, uuid.UUID(sooner["id"]))
        later_row = db.get(Payment, uuid.UUID(later["id"]))
        assert sooner_row.status == "paid"
        assert sooner_row.amount_paid_minor == 2_000_000
        assert later_row.status == "partially_paid"
        assert later_row.amount_paid_minor == 2_000_000

    # A second approval must not silently overwrite the first one.
    again = admin_client.post(f"/api/v1/accounting/receipts/{receipt['id']}/approve")
    assert again.status_code == 409


def test_overpayment_stays_as_credit_and_settles_the_balance(admin_client: TestClient) -> None:
    project = _employer(admin_client, 860002, name="پروژه اعتبار")
    invoice = _invoice(admin_client, project["id"], amount_minor=2_000_000)
    receipt = _receipt(admin_client, project["id"], amount=5_000_000)

    approved = admin_client.post(f"/api/v1/accounting/receipts/{receipt['id']}/approve")
    assert approved.status_code == 200, approved.text
    assert sum(row["amount_minor"] for row in approved.json()["allocations"]) == 2_000_000

    totals = _totals(admin_client, project["id"])
    assert totals["debt_minor"] == 0
    assert totals["credit_minor"] == 3_000_000
    assert totals["balance_minor"] == 0
    assert totals["settled"] is True

    with SessionLocal() as db:
        import uuid

        row = db.get(Payment, uuid.UUID(invoice["id"]))
        assert row.status == "paid"


def test_receipt_rejection_requires_a_reason_and_notifies_the_employer(
    admin_client: TestClient, mock_adapter
) -> None:
    project = _employer(admin_client, 860003, name="پروژه رد")
    _invoice(admin_client, project["id"])

    # The receipt is submitted by the employer, so the result reaches their chat.
    telegram_update(admin_client, telegram_id=860003, callback_data="0:rnew")
    telegram_update(admin_client, telegram_id=860003, text="1000000")
    telegram_update(admin_client, telegram_id=860003, text="/skip")
    telegram_update(admin_client, telegram_id=860003, text="رسید بانکی شماره ۱۲۳")

    with SessionLocal() as db:
        receipt = db.query(PaymentReceipt).one()
        receipt_id = str(receipt.id)
        assert receipt.member_id is not None

    too_short = admin_client.post(
        f"/api/v1/accounting/receipts/{receipt_id}/reject", json={"note": "بد"}
    )
    assert too_short.status_code == 400

    rejected = admin_client.post(
        f"/api/v1/accounting/receipts/{receipt_id}/reject",
        json={"note": "تصویر رسید خوانا نیست."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["review_note"] == "تصویر رسید خوانا نیست."

    run_worker(mock_adapter)
    texts = [message["text"] for message in mock_adapter.sent]
    rejection = [text for text in texts if "تصویر رسید خوانا نیست." in text]
    assert rejection, texts
    assert "رد" in rejection[-1]
    # The employer gets a shortcut back into the payment section.
    result = [
        message for message in mock_adapter.sent if "تصویر رسید خوانا نیست." in message["text"]
    ][-1]
    callbacks = [
        button["callback_data"] for row in result["keyboard"]["inline_keyboard"] for button in row
    ]
    assert any(callback.endswith(":fin") for callback in callbacks)

    totals = _totals(admin_client, project["id"])
    assert totals["debt_minor"] == 5_000_000
    assert totals["pending_receipts"] == 0


def test_allocations_can_be_edited_after_approval(admin_client: TestClient) -> None:
    project = _employer(admin_client, 860004, name="پروژه تخصیص")
    first = _invoice(admin_client, project["id"], title="اول", amount_minor=1_000_000)
    second = _invoice(admin_client, project["id"], title="دوم", amount_minor=4_000_000)
    receipt = _receipt(admin_client, project["id"], amount=2_000_000)
    admin_client.post(f"/api/v1/accounting/receipts/{receipt['id']}/approve")

    updated = admin_client.patch(
        f"/api/v1/accounting/receipts/{receipt['id']}/allocations",
        json={
            "allocations": [
                {"payment_id": second["id"], "amount_minor": 1_500_000},
                {"payment_id": first["id"], "amount_minor": 500_000},
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    assert {row["payment_id"]: row["amount_minor"] for row in updated.json()["allocations"]} == {
        first["id"]: 500_000,
        second["id"]: 1_500_000,
    }

    with SessionLocal() as db:
        import uuid

        assert db.get(Payment, uuid.UUID(first["id"])).amount_paid_minor == 500_000
        assert db.get(Payment, uuid.UUID(second["id"])).status == "partially_paid"

    # A single invoice can never receive more than its remaining amount.
    over = admin_client.patch(
        f"/api/v1/accounting/receipts/{receipt['id']}/allocations",
        json={"allocations": [{"payment_id": first["id"], "amount_minor": 1_500_000}]},
    )
    assert over.status_code == 400

    # Nor may the split exceed the receipt itself.
    over_receipt = admin_client.patch(
        f"/api/v1/accounting/receipts/{receipt['id']}/allocations",
        json={
            "allocations": [
                {"payment_id": first["id"], "amount_minor": 1_000_000},
                {"payment_id": second["id"], "amount_minor": 1_500_000},
            ]
        },
    )
    assert over_receipt.status_code == 400


def test_template_override_is_scoped_and_resettable(admin_client: TestClient) -> None:
    project = _employer(admin_client, 860005, name="پروژه متن")
    listing = admin_client.get("/api/v1/accounting/templates").json()
    keys = {row["key"] for row in listing}
    assert {"payment_instructions", "receipt_received", "license_delivery"} <= keys
    assert all(row["customized"] is False for row in listing)

    body = "<b>{project}</b>\nکارت: {cards}\nمبلغ: {amount}"
    saved = admin_client.put(
        "/api/v1/accounting/templates/payment_instructions", json={"body": body}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["customized"] is True

    scoped = admin_client.put(
        "/api/v1/accounting/templates/payment_instructions",
        json={"body": "متن پروژه {project}", "project_id": project["id"]},
    )
    assert scoped.status_code == 200, scoped.text

    from app.services.accounting import TemplateService

    with SessionLocal() as db:
        import uuid

        project_text = TemplateService.render(
            db,
            "payment_instructions",
            project_id=uuid.UUID(project["id"]),
            values={"project": "پروژه متن", "cards": "—", "amount": ""},
        )
        global_text = TemplateService.render(
            db,
            "payment_instructions",
            project_id=None,
            values={"project": "x", "cards": "—", "amount": ""},
        )
    assert project_text == "متن پروژه پروژه متن"
    assert global_text.startswith("<b>x</b>")

    reset = admin_client.delete(
        "/api/v1/accounting/templates/payment_instructions",
        params={"project_id": project["id"]},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["customized"] is False
    with SessionLocal() as db:
        import uuid

        assert (
            TemplateService.render(
                db,
                "payment_instructions",
                project_id=uuid.UUID(project["id"]),
                values={"project": "پروژه متن", "cards": "—", "amount": ""},
            )
            == "<b>پروژه متن</b>\nکارت: —\nمبلغ: "
        )


def test_bot_receipt_flow_creates_a_pending_receipt(admin_client: TestClient, mock_adapter) -> None:
    project = _employer(admin_client, 860006, name="پروژه رسید")
    _invoice(admin_client, project["id"], amount_minor=2_000_000)
    admin_client.post(
        "/api/v1/accounting/payment-methods",
        json={
            "project_id": project["id"],
            "title": "کارت واریز",
            "card_number": "6104337712345678",
        },
    )

    telegram_update(admin_client, telegram_id=860006, callback_data="0:rnew")
    instructions = mock_adapter.sent[-2]["text"]
    assert "6104337712345678" in instructions
    assert "مبلغ واریز شده" in last_message(mock_adapter)["text"]

    telegram_update(admin_client, telegram_id=860006, text="۲,۵۰۰,۰۰۰ تومان")
    assert "کد پیگیری" in last_message(mock_adapter)["text"]

    telegram_update(admin_client, telegram_id=860006, text="/skip")
    assert "تصویر رسید" in last_message(mock_adapter)["text"]

    telegram_update(admin_client, telegram_id=860006, text="/skip")
    confirmation = last_message(mock_adapter)["text"]
    assert "2,500,000 تومان" in confirmation
    buttons = [
        button["text"]
        for row in last_message(mock_adapter)["keyboard"]["inline_keyboard"]
        for button in row
    ]
    assert "سوابق واریز" in buttons

    with SessionLocal() as db:
        receipt = db.query(PaymentReceipt).one()
        assert receipt.amount_minor == 2_500_000
        assert receipt.status == "pending"
        assert receipt.channel == "telegram"
        assert receipt.member_id is not None

    telegram_update(admin_client, telegram_id=860006, callback_data="0:rhist")
    history = last_message(mock_adapter)["text"]
    assert "در انتظار بررسی" in history
    assert "2,500,000 تومان" in history


def test_bot_receipt_flow_rejects_bad_amounts(admin_client: TestClient, mock_adapter) -> None:
    _employer(admin_client, 860007, name="پروژه ورودی")
    telegram_update(admin_client, telegram_id=860007, callback_data="0:rnew")

    for bad in ("-۵۰۰", "صفر", "0", "12abc"):
        telegram_update(admin_client, telegram_id=860007, text=bad)
        assert "مبلغ را فقط با رقم بنویسید" in last_message(mock_adapter)["text"]

    telegram_update(admin_client, telegram_id=860007, text="/cancel")
    assert "لغو شد" in last_message(mock_adapter)["text"]
    with SessionLocal() as db:
        assert db.query(PaymentReceipt).count() == 0


def test_overview_reports_every_project(admin_client: TestClient) -> None:
    first = _employer(admin_client, 860008, name="پروژه اول")
    second = _employer(admin_client, 860009, name="پروژه دوم")
    _invoice(admin_client, first["id"], amount_minor=1_000_000)
    _invoice(admin_client, second["id"], amount_minor=2_000_000)

    overview = admin_client.get("/api/v1/accounting/overview").json()
    assert overview["totals"][0]["currency"] == "IRT"
    assert overview["totals"][0]["debt_minor"] == 3_000_000
    by_name = {row["project_name"]: row["totals"][0] for row in overview["projects"]}
    assert by_name["پروژه اول"]["debt_minor"] == 1_000_000
    assert by_name["پروژه دوم"]["debt_minor"] == 2_000_000
    assert by_name["پروژه دوم"]["settled"] is False


def test_cancelled_invoice_leaves_the_debt(admin_client: TestClient) -> None:
    project = _employer(admin_client, 860010, name="پروژه لغو")
    invoice = _invoice(admin_client, project["id"], amount_minor=1_000_000)
    cancelled = admin_client.post(f"/api/v1/payments/{invoice['id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    totals = _totals(admin_client, project["id"])
    assert totals["debt_minor"] == 0
    assert totals["settled"] is True


def test_pushed_announcement_carries_a_shortcut_button(
    admin_client: TestClient, mock_adapter
) -> None:
    project = _employer(admin_client, 860011, name="پروژه اطلاعیه")
    created = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={"title": "تحویل نسخه اول", "body": "نسخه اول آماده بازبینی است."},
    )
    assert created.status_code == 201, created.text

    run_worker(mock_adapter)
    pushed = [
        message
        for message in mock_adapter.sent
        if "تحویل نسخه اول" in message["text"] and message.get("keyboard")
    ]
    assert pushed, [message["text"] for message in mock_adapter.sent]
    callbacks = [
        button["callback_data"]
        for row in pushed[-1]["keyboard"]["inline_keyboard"]
        for button in row
    ]
    assert any(callback.endswith(":ann") for callback in callbacks)
    assert all(len(callback.encode("utf-8")) <= 64 for callback in callbacks)


def test_payment_reminder_carries_the_receipt_button(
    admin_client: TestClient, mock_adapter
) -> None:
    project = _employer(admin_client, 860012, name="پروژه یادآوری")
    _invoice(
        admin_client,
        project["id"],
        amount_minor=1_000_000,
        due_at=(utcnow() + timedelta(days=3)).isoformat(),
    )
    run_worker(mock_adapter)
    reminders = [
        message
        for message in mock_adapter.sent
        if "یادآوری پرداخت" in message["text"] and message.get("keyboard")
    ]
    assert reminders, [message["text"] for message in mock_adapter.sent]
    callbacks = [
        button["callback_data"]
        for row in reminders[-1]["keyboard"]["inline_keyboard"]
        for button in row
    ]
    assert any(callback.endswith(":rnew") for callback in callbacks)


def test_receipt_with_photo_notifies_admin_with_the_image(
    admin_client: TestClient, mock_adapter, monkeypatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "admin_telegram_chat_id", 555001)
    project = _employer(admin_client, 860013, name="پروژه تصویر رسید")
    _invoice(admin_client, project["id"], amount_minor=3_000_000)

    telegram_update(admin_client, telegram_id=860013, callback_data="0:rnew")
    telegram_update(admin_client, telegram_id=860013, text="1500000")
    telegram_update(admin_client, telegram_id=860013, text="/skip")
    # The photo's caption becomes the receipt note.
    telegram_update(admin_client, telegram_id=860013, photo=True, text="واریز از کارت خودم")

    with SessionLocal() as db:
        receipt = db.query(PaymentReceipt).one()
        assert receipt.status == "pending"
        assert receipt.note == "واریز از کارت خودم"
        assert len(receipt.files) == 1

    run_worker(mock_adapter)
    alerts = [
        message
        for message in mock_adapter.sent
        if message["chat_id"] == 555001 and "رسید پرداخت جدید" in message["text"]
    ]
    assert alerts, [(m["chat_id"], m["text"][:40]) for m in mock_adapter.sent]
    assert "1,500,000 تومان" in alerts[-1]["text"]
    media = [
        message
        for message in mock_adapter.sent
        if message["chat_id"] == 555001 and message.get("media")
    ]
    assert media, "the receipt image must be forwarded to the admin chat"
