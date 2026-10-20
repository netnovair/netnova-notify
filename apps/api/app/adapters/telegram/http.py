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

    def send_media(
        self,
        chat_id: int,
        data: bytes,
        filename: str,
        *,
        as_document: bool = False,
        caption: str | None = None,
    ) -> SendResult:
        """Upload an attachment as a photo or a document.

        Telegram caps a photo at 10 MB; anything bigger is sent as a document,
        which keeps the original bytes intact for the recipient.
        """
        field = "document" if as_document or len(data) > 10 * 1024 * 1024 else "photo"
        payload: dict = {"chat_id": str(chat_id)}
        if caption:
            payload["caption"] = caption[:1024]
            payload["parse_mode"] = "HTML"
        try:
            response = self._client.post(
                f"/send{field.capitalize()}",
                data=payload,
                files={field: (filename, data, "application/octet-stream")},
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise UnknownTelegramError(f"Telegram transport failure: {type(exc).__name__}") from exc
        if response.status_code == 200:
            body = response.json()
            if not body.get("ok"):
                raise PermanentTelegramError(str(body.get("description", "rejected")))
            result = body.get("result") or {}
            return SendResult(message_id=int(result.get("message_id") or 0))
        if response.status_code == 429 or response.status_code >= 500:
            raise TemporaryTelegramError(f"Telegram temporary error {response.status_code}")
        raise PermanentTelegramError(f"Telegram rejected the file {response.status_code}")

    def send_photo_url(
        self, chat_id: int, photo_url: str, caption: str | None = None
    ) -> SendResult:
        """Send a portfolio image by public URL.

        Telegram fetches the file itself, so the API never proxies or stores
        customer artwork. Only https URLs pass validation upstream.
        """
        payload: dict = {"chat_id": chat_id, "photo": photo_url}
        if caption:
            payload["caption"] = caption[:1024]
            payload["parse_mode"] = "HTML"
        result = self._call("sendPhoto", payload)
        return SendResult(message_id=int(result.get("message_id") or 0))

    def download_file(self, file_id: str, max_bytes: int) -> bytes:
        """Download a file the user sent to the bot.

        ``getFile`` only returns a path; the bytes live on a separate CDN host.
        The size is checked twice (before and after the download) so a malicious
        client cannot exhaust memory.
        """
        info = self._call("getFile", {"file_id": file_id})
        file_path = info.get("file_path")
        if not file_path:
            raise PermanentTelegramError("Telegram did not return a file path.")
        expected = int(info.get("file_size") or 0)
        if expected and expected > max_bytes:
            raise PermanentTelegramError("Telegram file is larger than the allowed size.")
        try:
            response = self._client.get(f"{API_BASE}/file/bot{self._token}/{file_path}")
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise UnknownTelegramError(f"Telegram transport failure: {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise PermanentTelegramError(f"Telegram file download failed {response.status_code}")
        data = response.content
        if len(data) > max_bytes:
            raise PermanentTelegramError("Telegram file is larger than the allowed size.")
        return data

    def set_my_commands(self, commands: list[dict]) -> bool:
        result = self._call("setMyCommands", {"commands": commands})
        return bool(result)

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
