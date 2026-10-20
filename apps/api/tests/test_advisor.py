from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import (
    activate_employer,
    approve_first_member,
    create_project,
    last_message,
    telegram_update,
)


def test_advisor_is_reported_as_unavailable_without_a_key(admin_client: TestClient) -> None:
    status = admin_client.get("/api/v1/advisor/status")
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["available"] is False
    assert body["provider"] == "none"
    assert "به زودی" in body["reason"]


def test_asking_the_advisor_never_fabricates_an_answer(admin_client: TestClient) -> None:
    response = admin_client.post("/api/v1/advisor/ask", json={"question": "چطور سئو کنم؟"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "advisor_unavailable"


def test_bot_advisor_button_says_coming_soon(admin_client: TestClient, mock_adapter) -> None:
    project = create_project(admin_client, name="پروژه مشاور")
    activate_employer(client=admin_client, code=project["license_code"], telegram_id=880001)
    approve_first_member(admin_client, project["id"])

    telegram_update(admin_client, telegram_id=880001, callback_data="0:advice")
    text = last_message(mock_adapter)["text"]
    assert "به زودی" in text
    # The employer is pointed at a channel that actually answers.
    assert "پشتیبانی" in text


def test_advisor_prompt_keeps_project_facts_and_limits(admin_client: TestClient) -> None:
    from app.domain.advisor import MAX_ANSWER_CHARS, build_prompt, clean_answer

    prompt = build_prompt("سوال", context="نام پروژه: آرمان")
    assert "نام پروژه: آرمان" in prompt
    assert "سوال" in prompt
    assert len(prompt) < 2500
    assert clean_answer("  پاسخ   کوتاه \n") == "پاسخ کوتاه"
    assert len(clean_answer("x" * (MAX_ANSWER_CHARS + 50))) == MAX_ANSWER_CHARS
