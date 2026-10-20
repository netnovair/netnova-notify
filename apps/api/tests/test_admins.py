from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings

settings = get_settings()


def _create_admin(admin_client: TestClient, email: str = "second@netnova.ir") -> dict:
    response = admin_client.post(
        "/api/v1/admins",
        json={"email": email, "display_name": "مدیر دوم", "password": "Second-Admin-Pass-1"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_admin_can_change_own_password_and_sessions_rotate(admin_client: TestClient) -> None:
    second = TestClient(admin_client.app)
    other = second.post(
        "/api/v1/auth/login",
        json={"email": settings.bootstrap_admin_email, "password": settings.bootstrap_admin_password},
    )
    assert other.status_code == 200
    other_token = other.cookies.get("nn_session")

    response = admin_client.post(
        "/api/v1/admins/me/password",
        json={
            "current_password": settings.bootstrap_admin_password,
            "new_password": "Rotated-Admin-Pass-77",
        },
    )
    assert response.status_code == 204, response.text

    # The current session survives...
    assert admin_client.get("/api/v1/auth/me").status_code == 200
    # ...while every other session of the same admin is revoked.
    if other_token:
        assert second.get("/api/v1/auth/me").status_code == 401

    # Old password no longer works, new one does.
    fresh = TestClient(admin_client.app)
    assert (
        fresh.post(
            "/api/v1/auth/login",
            json={
                "email": settings.bootstrap_admin_email,
                "password": settings.bootstrap_admin_password,
            },
        ).status_code
        == 401
    )
    assert (
        fresh.post(
            "/api/v1/auth/login",
            json={"email": settings.bootstrap_admin_email, "password": "Rotated-Admin-Pass-77"},
        ).status_code
        == 200
    )


def test_change_password_requires_current_password(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/api/v1/admins/me/password",
        json={"current_password": "wrong-password", "new_password": "Another-Pass-12345"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_current_password"


def test_admin_crud_and_guards(admin_client: TestClient) -> None:
    created = _create_admin(admin_client)
    assert created["is_active"] is True
    assert created["last_password_change_at"] is not None

    duplicate = admin_client.post(
        "/api/v1/admins",
        json={"email": "second@netnova.ir", "display_name": "تکراری", "password": "Second-Admin-Pass-1"},
    )
    assert duplicate.status_code == 409

    weak = admin_client.post(
        "/api/v1/admins",
        json={"email": "third@netnova.ir", "display_name": "ضعیف", "password": "short"},
    )
    assert weak.status_code == 422

    listed = admin_client.get("/api/v1/admins").json()
    assert {item["email"] for item in listed} >= {"second@netnova.ir"}

    deactivate = admin_client.patch(f"/api/v1/admins/{created['id']}", json={"is_active": False})
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    # A deactivated admin cannot log in (403 keeps the account visibly disabled,
    # it does not pretend the password was wrong).
    blocked = admin_client.post(
        "/api/v1/auth/login",
        json={"email": "second@netnova.ir", "password": "Second-Admin-Pass-1"},
    )
    assert blocked.status_code == 403

    me = admin_client.get("/api/v1/auth/me").json()["admin"]
    self_deactivate = admin_client.patch(f"/api/v1/admins/{me['id']}", json={"is_active": False})
    assert self_deactivate.status_code == 409


def test_reset_password_returns_temporary_and_revokes_sessions(admin_client: TestClient) -> None:
    created = _create_admin(admin_client, email="reset@netnova.ir")
    temp_client = TestClient(admin_client.app)
    login = temp_client.post(
        "/api/v1/auth/login",
        json={"email": "reset@netnova.ir", "password": "Second-Admin-Pass-1"},
    )
    assert login.status_code == 200
    token = login.cookies.get("nn_session")

    wrong_confirm = admin_client.post(
        f"/api/v1/admins/{created['id']}/reset-password",
        json={"confirm_email": "other@netnova.ir"},
    )
    assert wrong_confirm.status_code == 409

    reset = admin_client.post(
        f"/api/v1/admins/{created['id']}/reset-password",
        json={"confirm_email": "reset@netnova.ir"},
    )
    assert reset.status_code == 200, reset.text
    temporary = reset.json()["temporary_password"]
    assert len(temporary) >= 10

    if token:
        assert temp_client.get("/api/v1/auth/me").status_code == 401

    re_login = TestClient(admin_client.app).post(
        "/api/v1/auth/login", json={"email": "reset@netnova.ir", "password": temporary}
    )
    assert re_login.status_code == 200
