from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_login_me_and_logout(client: TestClient) -> None:
    settings = get_settings()
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.bootstrap_admin_email,
            "password": settings.bootstrap_admin_password,
        },
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["admin"]["email"] == settings.bootstrap_admin_email
    assert body["csrf_token"]
    cookie = login.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "nn_session=" in cookie

    client.headers["X-CSRF-Token"] = body["csrf_token"]
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["csrf_token"] == body["csrf_token"]

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200, logout.text
    assert client.get("/api/v1/auth/me").status_code == 401


def test_invalid_credentials_have_generic_message(client: TestClient) -> None:
    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "wrong-password"},
    )
    unknown_email = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@netnova.ir", "password": "wrong-password"},
    )
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json()["error"]["message"] == unknown_email.json()["error"]["message"]


def test_protected_endpoints_require_session(client: TestClient) -> None:
    for path in (
        "/api/v1/projects",
        "/api/v1/dashboard",
        "/api/v1/system/status",
        "/api/v1/notifications",
        "/api/v1/auth/me",
    ):
        response = client.get(path)
        assert response.status_code == 401, path


def test_csrf_is_required_for_mutations(admin_client: TestClient) -> None:
    token = admin_client.headers.pop("X-CSRF-Token")
    try:
        missing = admin_client.post(
            "/api/v1/projects", json={"name": "پروژه", "client_name": "کارفرما"}
        )
        assert missing.status_code == 403
        assert missing.json()["error"]["code"] == "csrf_failed"

        admin_client.headers["X-CSRF-Token"] = "not-the-right-token"
        wrong = admin_client.post(
            "/api/v1/projects", json={"name": "پروژه", "client_name": "کارفرما"}
        )
        assert wrong.status_code == 403
    finally:
        admin_client.headers["X-CSRF-Token"] = token


def test_login_rate_limit(client: TestClient) -> None:
    settings = get_settings()
    original = settings.login_rate_limit
    settings.login_rate_limit = 2
    try:
        for _ in range(2):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "admin@netnova.ir", "password": "bad-password"},
            )
            assert response.status_code == 401
        blocked = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@netnova.ir", "password": "bad-password"},
        )
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "rate_limited"
    finally:
        settings.login_rate_limit = original


def test_admin_bootstrap_status(client: TestClient) -> None:
    response = client.get("/api/v1/auth/bootstrap-status")
    assert response.status_code == 200
    assert response.json() == {"admin_configured": True}


def test_session_cookie_is_not_set_for_failed_login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@netnova.ir", "password": "wrong"},
    )
    assert "set-cookie" not in response.headers


def test_login_rejects_foreign_browser_origin(client: TestClient) -> None:
    settings = get_settings()
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.bootstrap_admin_email,
            "password": settings.bootstrap_admin_password,
        },
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_security_headers_and_no_store(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
