"""Real Telegram Bot API adapter (central bot token)."""

from __future__ import annotations

import logging

import httpx

from app.adapters.telegram.base import (
    PermanentTelegramError,
    SendResult,
    TemporaryTelegramError,
    UnknownTelegramError,
)

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"


class HttpTelegramAdapter:
    mode = "http"

    def __init__(self, token: str, timeout: float = 10.0) -> None:
        if not token:
            raise ValueError("A bot token is required for the HTTP adapter.")
        self._token = token
        self._client = httpx.Client(
            base_url=f"{API_BASE}/bot{token}",
            timeout=httpx.Timeout(timeout, connect=5.0),
        )

    def _call(self, method: str, payload: dict) -> dict:
        try:
            response = self._client.post(f"/{method}", json=payload)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            # The request may or may not have reached Telegram.
            raise UnknownTelegramError(f"Telegram transport failure: {type(exc).__name__}") from exc

        if response.status_code == 200:
            data = response.json()
            if not data.get("ok"):
                raise PermanentTelegramError(
                    str(data.get("description", "Telegram rejected the request"))
                )
            return data.get("result", {})

        description = ""
        retry_after: int | None = None
        try:
            body = response.json()
            description = str(body.get("description", ""))
            retry_after = body.get("parameters", {}).get("retry_after")
        except ValueError:
            description = response.text[:200]

        if response.status_code == 429 or response.status_code >= 500:
            raise TemporaryTelegramError(
                f"Telegram temporary error {response.status_code}: {description}",
                retry_after=retry_after,
            )
        raise PermanentTelegramError(
            f"Telegram rejected the request {response.status_code}: {description}"
        )

    def send_message(self, chat_id: int, text: str, keyboard: dict | None = None) -> SendResult:
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if keyboard:
            payload["reply_markup"] = keyboard
        result = self._call("sendMessage", payload)
        return SendResult(message_id=int(result["message_id"]))

    def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        payload: dict = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
            payload["show_alert"] = False
        try:
            self._call("answerCallbackQuery", payload)
        except Exception:  # noqa: BLE001 - callback acknowledgement is best effort
            logger.warning("Could not answer Telegram callback query.")

    def set_webhook(self, url: str, secret_token: str) -> bool:
        result = self._call(
            "setWebhook",
            {
                "url": url,
                "secret_token": secret_token,
                "allowed_updates": ["message", "callback_query"],
                "drop_pending_updates": False,
            },
        )
        return bool(result)

    def delete_webhook(self) -> bool:
        result = self._call("deleteWebhook", {"drop_pending_updates": False})
        return bool(result)

    def get_me(self) -> dict:
        return self._call("getMe", {})
