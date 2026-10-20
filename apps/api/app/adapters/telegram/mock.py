"""Mock Telegram adapter for development and tests.

No network call is made. The admin UI and delivery records mark these sends as
simulated, so mock output is never presented as a real Telegram delivery.
"""

from __future__ import annotations

import base64
import itertools
import logging
import threading

from app.adapters.telegram.base import SendResult

logger = logging.getLogger(__name__)

#: Smallest possible valid PNG (1x1, transparent); keeps the mock honest about
#: the magic-byte check without touching the network.
MOCK_IMAGE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGA"
    "hKmMIQAAAABJRU5ErkJggg=="
)


class MockTelegramAdapter:
    mode = "mock"

    def __init__(self) -> None:
        self._counter = itertools.count(1)
        self._lock = threading.Lock()
        self.sent: list[dict] = []
        #: file_id/max_bytes of every download_file call, for assertions.
        self.downloads: list[dict] = []

    def send_message(self, chat_id: int, text: str, keyboard: dict | None = None) -> SendResult:
        with self._lock:
            index = next(self._counter)
            self.sent.append(
                {"chat_id": chat_id, "text": text, "keyboard": keyboard, "mock_id": index}
            )
        logger.info("Mock Telegram message #%s to chat %s: %s", index, chat_id, text[:80])
        return SendResult(message_id=None, is_mock=True)

    def send_media(
        self,
        chat_id: int,
        data: bytes,
        filename: str,
        *,
        as_document: bool = False,
        caption: str | None = None,
    ) -> SendResult:
        with self._lock:
            index = next(self._counter)
            self.sent.append(
                {
                    "chat_id": chat_id,
                    "text": caption or "",
                    "keyboard": None,
                    "mock_id": index,
                    "media": {"filename": filename, "size": len(data), "document": as_document},
                }
            )
        logger.info("Mock Telegram file #%s (%s, %s bytes)", index, filename, len(data))
        return SendResult(message_id=None, is_mock=True)

    def send_photo_url(
        self, chat_id: int, photo_url: str, caption: str | None = None
    ) -> SendResult:
        with self._lock:
            index = next(self._counter)
            self.sent.append(
                {
                    "chat_id": chat_id,
                    "text": caption or "",
                    "keyboard": None,
                    "mock_id": index,
                    "photo": photo_url,
                }
            )
        logger.info("Mock Telegram photo #%s (%s)", index, photo_url)
        return SendResult(message_id=None, is_mock=True)

    def download_file(self, file_id: str, max_bytes: int) -> bytes:
        # A real 1x1 PNG so the same signature check runs as in production.
        self.downloads.append({"file_id": file_id, "max_bytes": max_bytes})
        return MOCK_IMAGE_PNG

    def set_my_commands(self, commands: list[dict]) -> bool:
        self.commands = list(commands)
        logger.info("Mock setMyCommands with %s commands", len(commands))
        return True

    def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        logger.info("Mock callback answer %s: %s", callback_query_id, text or "")

    def set_webhook(self, url: str, secret_token: str) -> bool:
        logger.info("Mock setWebhook to %s", url)
        return True

    def delete_webhook(self) -> bool:
        logger.info("Mock deleteWebhook")
        return True

    def get_me(self) -> dict:
        return {"username": "mock_bot", "id": 0, "is_mock": True}
