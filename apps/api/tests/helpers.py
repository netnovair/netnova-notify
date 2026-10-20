from __future__ import annotations

import itertools
import time

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.worker.runner import Worker

settings = get_settings()
_update_ids = itertools.count(1)


def auth_headers() -> dict[str, str]:
    return {"X-Telegram-Bot-Api-Secret-Token": settings.telegram_webhook_secret}


def create_project(
    admin_client: TestClient,
    *,
    name: str = "پروژه تست",
    client_name: str = "کارفرمای تست",
    slug: str | None = None,
) -> dict:
    payload: dict = {"name": name, "client_name": client_name}
    if slug:
        payload["slug"] = slug
    response = admin_client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def activate_employer(
    client: TestClient,
    *,
    code: str,
    telegram_id: int = 900001,
    username: str = "employer",
    first_name: str = "کارفرما",
) -> int:
    response = client.post(
        "/api/v1/licenses/activate",
        json={
            "code": code,
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
        },
        headers=auth_headers(),
    )
    assert response.status_code == 200, response.text
    return telegram_id


def approve_first_member(admin_client: TestClient, project_id: str) -> dict:
    members = admin_client.get(f"/api/v1/projects/{project_id}/members")
    assert members.status_code == 200, members.text
    pending = [item for item in members.json() if item["status"] == "pending_approval"]
    assert pending, members.json()
    response = admin_client.post(
        f"/api/v1/projects/{project_id}/members/{pending[0]['id']}/approve"
    )
    assert response.status_code == 200, response.text
    return response.json()


def telegram_update(
    client: TestClient,
    *,
    telegram_id: int,
    text: str | None = None,
    callback_data: str | None = None,
    photo: bool = False,
) -> int:
    update_id = next(_update_ids) + int(time.time()) * 1000
    sender = {
        "id": telegram_id,
        "is_bot": False,
        "first_name": "کارفرما",
        "username": "employer",
        "language_code": "fa",
    }
    if callback_data is not None:
        payload = {
            "update_id": update_id,
            "callback_query": {
                "id": f"cb-{update_id}",
                "from": sender,
                "message": {
                    "message_id": 10,
                    "chat": {"id": telegram_id, "type": "private"},
                    "date": int(time.time()),
                    "text": "menu",
                },
                "data": callback_data,
            },
        }
    elif photo:
        message = {
            "message_id": 1,
            "from": sender,
            "chat": {"id": telegram_id, "type": "private"},
            "date": int(time.time()),
            "photo": [
                {"file_id": "mock-photo-small", "file_unique_id": "u-small", "file_size": 500},
                {"file_id": "mock-photo-large", "file_unique_id": "u-large", "file_size": 4000},
            ],
        }
        if text:
            message["caption"] = text
        payload = {"update_id": update_id, "message": message}
    else:
        payload = {
            "update_id": update_id,
            "message": {
                "message_id": 1,
                "from": sender,
                "chat": {"id": telegram_id, "type": "private"},
                "date": int(time.time()),
                "text": text or "/start",
            },
        }
    response = client.post("/api/v1/telegram/webhook", json=payload, headers=auth_headers())
    assert response.status_code == 200, response.text
    return update_id


def make_jobs_due() -> None:
    with SessionLocal() as db:
        db.execute(
            text(
                "UPDATE scheduled_jobs SET run_at = now() - interval '1 second' WHERE status='pending'"
            )
        )
        db.commit()


def run_worker(mock_adapter) -> int:
    make_jobs_due()
    worker = Worker(settings=settings, adapter=mock_adapter)
    return worker.run_once(max_batches=20)


def last_message(mock_adapter) -> dict:
    assert mock_adapter.sent, "no mock Telegram message was sent"
    return mock_adapter.sent[-1]
