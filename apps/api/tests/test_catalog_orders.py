from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.catalog import ServiceRequest
from app.models.telegram import TelegramUser
from tests.helpers import last_message, telegram_update

GRAPHIC = 0
LOGO = 0
BUSINESS_CARD = 1
CONTENT = 3
CONTENT_ARTICLE_FA = 0


def _seed_catalog(admin_client: TestClient) -> dict:
    response = admin_client.post("/api/v1/catalog/seed")
    assert response.status_code == 200, response.text
    return response.json()


def _start_order(admin_client: TestClient, telegram_id: int) -> None:
    telegram_update(admin_client, telegram_id=telegram_id, text="/start")
    telegram_update(admin_client, telegram_id=telegram_id, callback_data="o:home")


def _pick(admin_client: TestClient, telegram_id: int, data: str) -> None:
    telegram_update(admin_client, telegram_id=telegram_id, callback_data=data)


def _register_contact(admin_client: TestClient, telegram_id: int, name: str, phone: str) -> None:
    telegram_update(admin_client, telegram_id=telegram_id, text=name)
    telegram_update(admin_client, telegram_id=telegram_id, text=phone)


def _button_labels(message: dict) -> list[str]:
    keyboard = message.get("keyboard") or {}
    return [button["text"] for row in keyboard.get("inline_keyboard", []) for button in row]


def _order_rows() -> list[ServiceRequest]:
    with SessionLocal() as db:
        return list(db.scalars(select(ServiceRequest).order_by(ServiceRequest.created_at)).all())


# ---------------------------------------------------------------------------
# Catalog CRUD
# ---------------------------------------------------------------------------
def test_catalog_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/catalog").status_code == 401
    assert client.get("/api/v1/orders").status_code == 401


def test_catalog_crud_is_reflected_in_the_bot_immediately(admin_client: TestClient, mock_adapter):
    category = admin_client.post(
        "/api/v1/catalog/categories",
        json={
            "key": "test-service",
            "title": "خدمت آزمایشی",
            "description": "دسته ساخته شده از پنل",
            "emoji": "🧪",
        },
    )
    assert category.status_code == 201, category.text
    category_id = category.json()["id"]

    item = admin_client.post(
        f"/api/v1/catalog/categories/{category_id}/items",
        json={
            "key": "test-item",
            "title": "زیرخدمت آزمایشی",
            "questions": [
                {"key": "budget", "label": "بودجه تقریبی", "field_type": "text"},
                {
                    "key": "deadline",
                    "label": "زمان تحویل",
                    "field_type": "choice",
                    "options": ["فوری", "عادی"],
                },
            ],
        },
    )
    assert item.status_code == 201, item.text
    assert [q["key"] for q in item.json()["questions"]] == ["budget", "deadline"]

    telegram_update(admin_client, telegram_id=700111, text="/start")
    _pick(admin_client, 700111, "o:home")
    assert any("خدمت آزمایشی" in label for label in _button_labels(last_message(mock_adapter)))

    # A panel edit must be visible on the very next bot interaction.
    updated = admin_client.patch(
        f"/api/v1/catalog/categories/{category_id}",
        json={"key": "test-service", "title": "خدمت آزمایشی ویرایش شده", "emoji": "🧪"},
    )
    assert updated.status_code == 200, updated.text
    _pick(admin_client, 700111, "o:home")
    assert any(
        "خدمت آزمایشی ویرایش شده" in label for label in _button_labels(last_message(mock_adapter))
    )

    deleted = admin_client.delete(f"/api/v1/catalog/categories/{category_id}")
    assert deleted.status_code == 204, deleted.text
    _pick(admin_client, 700111, "o:home")
    assert not any(
        "خدمت آزمایشی ویرایش شده" in label for label in _button_labels(last_message(mock_adapter))
    )


def test_choice_question_needs_two_options(admin_client: TestClient) -> None:
    category = admin_client.post("/api/v1/catalog/categories", json={"title": "دسته اعتبارسنجی"})
    assert category.status_code == 201, category.text
    response = admin_client.post(
        f"/api/v1/catalog/categories/{category.json()['id']}/items",
        json={
            "title": "زیرخدمت",
            "questions": [{"label": "انتخاب", "field_type": "choice", "options": ["فقط یکی"]}],
        },
    )
    assert response.status_code == 422, response.text


def test_cannot_delete_a_service_that_has_orders(admin_client: TestClient, mock_adapter) -> None:
    catalog = _seed_catalog(admin_client)
    assert catalog["public_categories"] == 5
    graphic = next(row for row in catalog["categories"] if row["key"] == "graphic")

    _start_order(admin_client, 700222)
    _pick(admin_client, 700222, f"oi:{GRAPHIC}:{LOGO}")
    _register_contact(admin_client, 700222, "مریم احمدی", "09121112233")
    _pick(admin_client, 700222, "oq:1:0")  # existing logo: yes
    _pick(admin_client, 700222, "oq:2:0")  # style
    _pick(admin_client, 700222, "oskip")  # optional colours
    _pick(admin_client, 700222, "oskip")  # optional details
    _pick(admin_client, 700222, "osubmit")

    rows = _order_rows()
    assert len(rows) == 1
    assert rows[0].item_title == graphic["items"][0]["title"]

    guarded = admin_client.delete(f"/api/v1/catalog/items/{graphic['items'][0]['id']}")
    assert guarded.status_code == 409, guarded.text
    assert "غیرفعال" in guarded.json()["error"]["message"]

    # Deactivating instead of deleting hides the item from the bot.
    deactivated = admin_client.patch(
        f"/api/v1/catalog/items/{graphic['items'][0]['id']}",
        json={
            "key": graphic["items"][0]["key"],
            "title": graphic["items"][0]["title"],
            "is_active": False,
        },
    )
    assert deactivated.status_code == 200, deactivated.text
    _pick(admin_client, 700222, "o:home")
    _pick(admin_client, 700222, f"oc:{GRAPHIC}")
    assert graphic["items"][0]["title"] not in _button_labels(last_message(mock_adapter))


# ---------------------------------------------------------------------------
# Bot order flow
# ---------------------------------------------------------------------------
def test_order_flow_collects_answers_and_reuses_identity(
    admin_client: TestClient, mock_adapter
) -> None:
    _seed_catalog(admin_client)

    telegram_update(admin_client, telegram_id=700333, text="/start")
    assert "ثبت سفارش" in last_message(mock_adapter)["text"]

    _pick(admin_client, 700333, "o:home")
    menu = last_message(mock_adapter)
    assert any("خدمات گرافیکی" in label for label in _button_labels(menu))
    assert any(
        button["callback_data"] == f"oc:{GRAPHIC}"
        for row in menu["keyboard"]["inline_keyboard"]
        for button in row
    )

    _pick(admin_client, 700333, f"oc:{GRAPHIC}")
    assert "طراحی لوگو" in _button_labels(last_message(mock_adapter))
    _pick(admin_client, 700333, f"oi:{GRAPHIC}:{LOGO}")
    assert "نام و نام خانوادگی" in last_message(mock_adapter)["text"]

    # Digits are rejected for a name; the flow repeats the question.
    telegram_update(admin_client, telegram_id=700333, text="کاربر 123")
    assert "نباید شامل عدد" in last_message(mock_adapter)["text"]

    _register_contact(admin_client, 700333, "رضا کریمی", "۰۹۱۲۳۴۵۶۷۸۹")
    assert "سوال ۱ از" in last_message(mock_adapter)["text"]

    telegram_update(admin_client, telegram_id=700333, text="فروشگاه لوازم خانگی")
    _pick(admin_client, 700333, "oq:1:1")  # no current logo
    _pick(admin_client, 700333, "oq:2:2")  # modern style
    _pick(admin_client, 700333, "oskip")
    _pick(admin_client, 700333, "oskip")
    assert "بازبینی سفارش" in last_message(mock_adapter)["text"]

    _pick(admin_client, 700333, "osubmit")
    confirmation = last_message(mock_adapter)
    assert "سفارش شما ثبت شد" in confirmation["text"]

    rows = _order_rows()
    assert len(rows) == 1
    request = rows[0]
    assert request.contact_name == "رضا کریمی"
    assert request.contact_phone == "09123456789"
    assert request.status == "new"
    assert request.telegram_id == 700333
    answered = {answer["key"]: answer["value"] for answer in request.answers}
    assert answered["field"] == "فروشگاه لوازم خانگی"
    assert answered["existing"] == "لوگو ندارم"

    # Identity is stored once and the next order starts straight from the questions.
    _start_order(admin_client, 700333)
    _pick(admin_client, 700333, f"oi:{GRAPHIC}:{BUSINESS_CARD}")
    assert "سوال ۱ از" in last_message(mock_adapter)["text"]
    with SessionLocal() as db:
        user = db.scalar(select(TelegramUser).where(TelegramUser.telegram_id == 700333))
        assert user is not None
        assert user.contact_name == "رضا کریمی"
        assert user.contact_phone == "09123456789"

    # A cancelled order leaves nothing behind.
    _pick(admin_client, 700333, "ox")
    assert "لغو شد" in last_message(mock_adapter)["text"]


def test_content_orders_require_at_least_800_words(admin_client: TestClient, mock_adapter) -> None:
    _seed_catalog(admin_client)
    _start_order(admin_client, 700444)
    _pick(admin_client, 700444, f"oc:{CONTENT}")
    _pick(admin_client, 700444, f"oi:{CONTENT}:{CONTENT_ARTICLE_FA}")
    _register_contact(admin_client, 700444, "سارا نادری", "09351112233")

    _pick(admin_client, 700444, "oq:0:0")  # Persian
    telegram_update(admin_client, telegram_id=700444, text="500")
    assert "حداقل مقدار مجاز ۸۰۰" in last_message(mock_adapter)["text"]

    with SessionLocal() as db:
        assert db.scalar(select(ServiceRequest)) is None

    telegram_update(admin_client, telegram_id=700444, text="۱۲۰۰")
    assert "تعداد مقالات" in last_message(mock_adapter)["text"]


def test_portfolio_button_shows_panel_managed_text(admin_client: TestClient, mock_adapter) -> None:
    catalog = _seed_catalog(admin_client)
    graphic = next(row for row in catalog["categories"] if row["key"] == "graphic")
    updated = admin_client.patch(
        f"/api/v1/catalog/categories/{graphic['id']}",
        json={
            "key": graphic["key"],
            "title": graphic["title"],
            "show_portfolio": True,
            "portfolio_text": "نمونه لوگوی فروشگاه مواد غذایی و برند پوشاک",
            "portfolio_url": "https://example.com/samples/logo.jpg",
        },
    )
    assert updated.status_code == 200, updated.text

    telegram_update(admin_client, telegram_id=700555, text="/start")
    _pick(admin_client, 700555, "pf")
    assert "نمونه کارها" in last_message(mock_adapter)["text"]
    _pick(admin_client, 700555, f"op:{GRAPHIC}")
    photo = next(
        (entry for entry in reversed(mock_adapter.sent) if entry.get("photo")),
        None,
    )
    assert photo is not None, "portfolio image was not sent"
    assert photo["photo"] == "https://example.com/samples/logo.jpg"
    assert "نمونه لوگوی فروشگاه" in photo["text"]

    # Non-https image urls are rejected before they reach Telegram.
    rejected = admin_client.patch(
        f"/api/v1/catalog/categories/{graphic['id']}",
        json={
            "key": graphic["key"],
            "title": graphic["title"],
            "portfolio_url": "http://insecure.example.com/a.jpg",
        },
    )
    assert rejected.status_code == 422


def test_seed_never_overwrites_an_existing_catalog(admin_client: TestClient) -> None:
    _seed_catalog(admin_client)
    again = _seed_catalog(admin_client)
    assert again["public_categories"] == 5
    assert len(again["categories"]) == 5


# ---------------------------------------------------------------------------
# Orders API
# ---------------------------------------------------------------------------
def test_orders_api_lists_filters_and_updates_status(
    admin_client: TestClient, mock_adapter
) -> None:
    _seed_catalog(admin_client)
    _start_order(admin_client, 700666)
    _pick(admin_client, 700666, f"oc:{CONTENT}")
    _pick(admin_client, 700666, f"oi:{CONTENT}:{CONTENT_ARTICLE_FA}")
    _register_contact(admin_client, 700666, "محمد رحیمی", "09127778899")
    _pick(admin_client, 700666, "oq:0:0")
    telegram_update(admin_client, telegram_id=700666, text="900")
    telegram_update(admin_client, telegram_id=700666, text="2")
    telegram_update(admin_client, telegram_id=700666, text="لوازم ورزشی")
    _pick(admin_client, 700666, "oskip")  # site address
    _pick(admin_client, 700666, "oq:5:0")  # topic is known
    _pick(admin_client, 700666, "osubmit")

    listing = admin_client.get("/api/v1/orders")
    assert listing.status_code == 200, listing.text
    payload = listing.json()
    assert payload["total"] == 1
    request = payload["items"][0]
    assert request["contact_phone"] == "09127778899"
    assert request["status"] == "new"

    detail = admin_client.get(f"/api/v1/orders/{request['id']}")
    assert detail.status_code == 200
    assert {answer["key"] for answer in detail.json()["answers"]} >= {
        "language",
        "words",
        "articles",
        "field",
    }

    updated = admin_client.patch(
        f"/api/v1/orders/{request['id']}",
        json={"status": "contacted", "admin_note": "تماس اولیه انجام شد."},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "contacted"
    assert updated.json()["admin_note"] == "تماس اولیه انجام شد."

    invalid = admin_client.patch(f"/api/v1/orders/{request['id']}", json={"status": "bypass"})
    assert invalid.status_code == 422

    counters = admin_client.get("/api/v1/orders/counters").json()
    assert counters["new"] == 0
    assert counters["contacted"] == 1
    assert counters["total"] == 1

    filtered = admin_client.get("/api/v1/orders", params={"status": "contacted"})
    assert filtered.json()["total"] == 1
    search = admin_client.get("/api/v1/orders", params={"search": "رحیمی"})
    assert search.json()["total"] == 1
    assert admin_client.get("/api/v1/orders", params={"search": "ناموجود"}).json()["total"] == 0
