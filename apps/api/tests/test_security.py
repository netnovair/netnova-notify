from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.rate_limit import rate_limiter
from tests.helpers import (
    activate_employer,
    approve_first_member,
    auth_headers,
    create_project,
    last_message,
    telegram_update,
)


def _prepare_project(admin_client: TestClient, name: str, telegram_id: int) -> dict:
    project = create_project(admin_client, name=name)
    activate_employer(client=admin_client, code=project["license_code"], telegram_id=telegram_id)
    approve_first_member(admin_client, project["id"])
    return project


def test_webhook_requires_correct_secret(admin_client: TestClient, mock_adapter) -> None:
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {"id": 1, "is_bot": False, "first_name": "x"},
            "chat": {"id": 1, "type": "private"},
            "date": 1,
            "text": "/start",
        },
    }
    assert admin_client.post("/api/v1/telegram/webhook", json=payload).status_code == 403
    bad = admin_client.post(
        "/api/v1/telegram/webhook",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert bad.status_code == 403
    assert not mock_adapter.sent


def test_group_chats_are_ignored(admin_client: TestClient, mock_adapter) -> None:
    payload = {
        "update_id": 2,
        "message": {
            "message_id": 1,
            "from": {"id": 55, "is_bot": False, "first_name": "x"},
            "chat": {"id": -100123, "type": "group"},
            "date": 1,
            "text": "/start",
        },
    }
    response = admin_client.post("/api/v1/telegram/webhook", json=payload, headers=auth_headers())
    assert response.status_code == 200
    assert not mock_adapter.sent


def test_employer_cannot_reach_another_project_via_callback(
    admin_client: TestClient, mock_adapter
) -> None:
    project_a = _prepare_project(admin_client, "پروژه الف", 820001)
    _prepare_project(admin_client, "پروژه ب", 820002)

    telegram_update(admin_client, telegram_id=820001, callback_data="1:ann")
    message = last_message(mock_adapter)
    assert "دسترسی شما به این پروژه فعال نیست" in message["text"]
    assert "پروژه ب" not in message["text"]

    telegram_update(admin_client, telegram_id=820001, callback_data="0:ann")
    message = last_message(mock_adapter)
    assert project_a["name"] in message["text"]


def test_client_cannot_override_delivery_destination(
    admin_client: TestClient, mock_adapter
) -> None:
    project = _prepare_project(admin_client, "پروژه مقصد", 820010)
    create = admin_client.post(
        f"/api/v1/projects/{project['id']}/notifications",
        json={
            "title": "اطلاعیه",
            "body": "متن",
            "chat_id": 999999,
            "telegram_id": 999999,
        },
    )
    assert create.status_code == 201, create.text
    from tests.helpers import run_worker

    run_worker(mock_adapter)
    notification_messages = [m for m in mock_adapter.sent if "اطلاعیه" in m["text"]]
    assert notification_messages
    assert notification_messages[-1]["chat_id"] == 820010
    assert all(message["chat_id"] != 999999 for message in mock_adapter.sent)


def test_inactive_project_stops_employer_access(admin_client: TestClient, mock_adapter) -> None:
    project = _prepare_project(admin_client, "پروژه غیرفعال شدنی", 820020)
    admin_client.patch(f"/api/v1/projects/{project['id']}", json={"status": "inactive"})
    telegram_update(admin_client, telegram_id=820020, text="/start")
    text = last_message(mock_adapter)["text"]
    assert project["name"] not in text
    assert "کد لایسنس" in text


def test_callback_with_unknown_data_is_rejected(admin_client: TestClient, mock_adapter) -> None:
    _prepare_project(admin_client, "پروژه امن", 820030)
    mock_adapter.sent.clear()
    telegram_update(admin_client, telegram_id=820030, callback_data="0:delete_everything")
    assert not mock_adapter.sent
    telegram_update(admin_client, telegram_id=820030, callback_data="s:performance")
    assert not mock_adapter.sent


def test_audit_log_for_sensitive_actions(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه حسابرسی")
    revoke = admin_client.post(
        f"/api/v1/licenses/{project['license']['id']}/revoke", json={"reason": "test"}
    )
    assert revoke.status_code == 200
    logs = admin_client.get(f"/api/v1/projects/{project['id']}/audit-logs")
    assert logs.status_code == 200, logs.text
    body = logs.json()
    actions = {item["action"] for item in body["items"]}
    assert "project.created" in actions
    assert "license.issued" in actions
    assert "license.revoked" in actions
    serialized = logs.text
    assert project["license_code"] not in serialized
    assert all(item["action_label"] for item in body["items"])


def test_activation_attempts_are_rate_limited(client: TestClient, admin_client: TestClient) -> None:
    project = create_project(admin_client)
    telegram_id = 820040
    for _ in range(3):
        telegram_update(client, telegram_id=telegram_id, text="NN-AAAA-BBBB-CCCC-DDDD")
    rate_limiter.reset()
    # A real code still activates (rate limiter only blocks brute force bursts).
    response = client.post(
        "/api/v1/licenses/activate",
        json={"code": project["license_code"], "telegram_id": telegram_id},
        headers=auth_headers(),
    )
    assert response.status_code == 200


def test_license_activation_rate_limit_message(admin_client: TestClient, mock_adapter) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.activation_rate_limit
    settings.activation_rate_limit = 2
    try:
        telegram_id = 820050
        for _ in range(3):
            telegram_update(admin_client, telegram_id=telegram_id, text="NN-XXXX-XXXX-XXXX-XXXX")
        assert "بیش از حد مجاز" in last_message(mock_adapter)["text"]
    finally:
        settings.activation_rate_limit = original
        rate_limiter.reset()


def test_foreign_origin_is_rejected_on_login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "Test-Admin-Pass-123"},
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_trusted_origin_is_accepted_on_login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "Test-Admin-Pass-123"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200


def test_dev_preview_origin_regex_only_applies_in_development(
    client: TestClient, monkeypatch
) -> None:
    from app.core.config import Settings

    preview = "https://3000-abc123.e2b.app"
    dev = Settings(
        _env_file=None,
        environment="development",
        dev_preview_origin_regex=r"https://[0-9]+-[a-z0-9]+\.e2b\.app",
        next_public_site_url="",
    )
    import app.api.deps as deps

    monkeypatch.setattr(deps, "get_settings", lambda: dev)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "Test-Admin-Pass-123"},
        headers={"Origin": preview},
    )
    assert response.status_code == 200

    production = Settings(
        _env_file=None,
        environment="production",
        dev_preview_origin_regex=r"https://[0-9]+-[a-z0-9]+\.e2b\.app",
        next_public_site_url="",
        secret_key="a" * 48,
        cookie_secure=True,
        telegram_webhook_secret="b" * 32,
    )
    monkeypatch.setattr(deps, "get_settings", lambda: production)
    rejected = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "Test-Admin-Pass-123"},
        headers={"Origin": preview},
    )
    assert rejected.status_code == 403


def _cookie_attributes(response) -> set[str]:
    raw = response.headers.get("set-cookie", "")
    return {part.strip().lower() for part in raw.split(";")}


def test_dev_preview_session_cookie_is_usable_inside_a_third_party_iframe(
    client: TestClient, monkeypatch
) -> None:
    """A hosted preview is embedded in another site, so a Lax cookie is dropped.

    The preview session must be SameSite=None + Secure + Partitioned, otherwise
    the login POST succeeds and every following API call is anonymous.
    """
    import app.api.deps as deps
    import app.api.v1.auth as auth_module
    from app.core.config import Settings

    preview = "https://3000-abc123.e2b.app"
    dev = Settings(
        _env_file=None,
        environment="development",
        dev_preview_origin_regex=r"https://[0-9]+-[a-z0-9]+\.e2b\.app",
        next_public_site_url="",
    )
    monkeypatch.setattr(deps, "get_settings", lambda: dev)
    monkeypatch.setattr(auth_module, "get_settings", lambda: dev)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "Test-Admin-Pass-123"},
        headers={"Origin": preview},
    )
    assert response.status_code == 200
    attributes = _cookie_attributes(response)
    assert "samesite=none" in attributes
    assert "secure" in attributes
    assert "partitioned" in attributes


def test_default_session_cookie_stays_same_site_lax(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "Test-Admin-Pass-123"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    attributes = _cookie_attributes(response)
    assert "samesite=lax" in attributes
    assert "partitioned" not in attributes


def test_dev_preview_bearer_fallback_authenticates_without_the_cookie(
    client: TestClient, monkeypatch
) -> None:
    """Browsers that block third-party cookies must still be able to use a preview.

    The login response carries a development-only token and the API accepts it in
    an ``Authorization: Bearer`` header from a matching preview host only.
    """
    import app.api.deps as deps
    from app.core.config import Settings

    preview = "https://3000-abc123.e2b.app"
    dev = Settings(
        _env_file=None,
        environment="development",
        dev_preview_origin_regex=r"https://[0-9]+-[a-z0-9]+\.e2b\.app",
        next_public_site_url="",
    )
    monkeypatch.setattr(deps, "get_settings", lambda: dev)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "Test-Admin-Pass-123"},
        headers={"Origin": preview},
    )
    assert response.status_code == 200
    token = response.json()["dev_session_token"]
    assert token

    # Simulate a browser that silently drops the cookie.
    client.cookies.clear()
    anonymous = client.get("/api/v1/dashboard", headers={"Host": "3000-abc123.e2b.app"})
    assert anonymous.status_code == 401

    authenticated = client.get(
        "/api/v1/dashboard",
        headers={
            "Authorization": f"Bearer {token}",
            "Host": "3000-abc123.e2b.app",
        },
    )
    assert authenticated.status_code == 200


def test_bearer_fallback_is_rejected_outside_the_dev_preview(
    admin_client: TestClient,
) -> None:
    token = admin_client.cookies.get("nn_session")
    assert token
    admin_client.cookies.clear()
    response = admin_client.get(
        "/api/v1/dashboard",
        headers={"Authorization": f"Bearer {token}", "Origin": "http://localhost:3000"},
    )
    assert response.status_code == 401


def test_production_never_returns_the_dev_session_token(client: TestClient, monkeypatch) -> None:
    import app.api.deps as deps
    from app.core.config import Settings

    production = Settings(
        _env_file=None,
        environment="production",
        dev_preview_origin_regex=r"https://[0-9]+-[a-z0-9]+\.e2b\.app",
        next_public_site_url="",
        secret_key="a" * 48,
        cookie_secure=True,
        telegram_webhook_secret="b" * 32,
    )
    monkeypatch.setattr(deps, "get_settings", lambda: production)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "Test-Admin-Pass-123"},
        headers={"Host": "3000-abc123.e2b.app"},
    )
    # The production settings require COOKIE_SECURE; the response must not leak a token.
    assert response.json().get("dev_session_token") is None


def test_development_always_returns_a_bearer_token_even_without_origin(
    client: TestClient, monkeypatch
) -> None:
    """Host detection must never gate the fallback: the preview proxy may rewrite Host."""
    import app.api.deps as deps
    import app.api.v1.auth as auth_module
    from app.core.config import Settings

    dev = Settings(
        _env_file=None,
        environment="development",
        dev_preview_origin_regex="",
        next_public_site_url="",
    )
    monkeypatch.setattr(deps, "get_settings", lambda: dev)
    monkeypatch.setattr(auth_module, "get_settings", lambda: dev)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "Test-Admin-Pass-123"},
    )
    assert response.status_code == 200
    token = response.json()["dev_session_token"]
    assert token

    client.cookies.clear()
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )


def test_stale_cookie_does_not_block_a_valid_bearer_token(client: TestClient, monkeypatch) -> None:
    """A leftover cookie from an earlier attempt must not win over a good token."""
    import app.api.deps as deps
    import app.api.v1.auth as auth_module
    from app.core.config import Settings

    dev = Settings(_env_file=None, environment="development", next_public_site_url="")
    monkeypatch.setattr(deps, "get_settings", lambda: dev)
    monkeypatch.setattr(auth_module, "get_settings", lambda: dev)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "Test-Admin-Pass-123"},
    )
    token = response.json()["dev_session_token"]
    client.cookies.set("nn_session", "stale-or-garbage-token")
    authenticated = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert authenticated.status_code == 200


def test_dev_preview_accepts_the_custom_session_header(client: TestClient, monkeypatch) -> None:
    """Preview proxies may strip Authorization, so a custom header is accepted too."""
    import app.api.deps as deps
    import app.api.v1.auth as auth_module
    from app.core.config import Settings

    dev = Settings(_env_file=None, environment="development", next_public_site_url="")
    monkeypatch.setattr(deps, "get_settings", lambda: dev)
    monkeypatch.setattr(auth_module, "get_settings", lambda: dev)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "Test-Admin-Pass-123"},
    )
    token = response.json()["dev_session_token"]
    client.cookies.clear()
    assert client.get("/api/v1/auth/me", headers={"X-NN-Session": token}).status_code == 200
    assert client.get("/api/v1/dashboard", headers={"X-NN-Session": token}).status_code == 200


def test_custom_session_header_is_rejected_outside_development(admin_client: TestClient) -> None:
    token = admin_client.cookies.get("nn_session")
    admin_client.cookies.clear()
    assert admin_client.get("/api/v1/auth/me", headers={"X-NN-Session": token}).status_code == 401
