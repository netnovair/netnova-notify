"""Telegram adapter contract and error taxonomy.

The delivery policy depends on classifying failures correctly:

* ``TemporaryTelegramError`` - Telegram rejected the request without sending
  (429 / 5xx). Safe to retry.
* ``PermanentTelegramError`` - invalid chat, blocked bot, malformed message.
  Retrying cannot help.
* ``UnknownTelegramError`` - timeout or transport failure after the request may
  have reached Telegram. We must NOT treat it as success and we do NOT retry
  automatically, because that could duplicate the message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TelegramError(Exception):
    """Base class for adapter errors."""


class TemporaryTelegramError(TelegramError):
    def __init__(self, message: str, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(message)


class PermanentTelegramError(TelegramError):
    pass


class UnknownTelegramError(TelegramError):
    """Outcome of the request is unknown (timeout / connection reset)."""


@dataclass(frozen=True)
class SendResult:
    message_id: int | None
    is_mock: bool = False


class TelegramAdapter(Protocol):
    mode: str

    def send_message(self, chat_id: int, text: str, keyboard: dict | None = None) -> SendResult: ...

    def send_media(
        self,
        chat_id: int,
        data: bytes,
        filename: str,
        *,
        as_document: bool = False,
        caption: str | None = None,
    ) -> SendResult: ...

    def send_photo_url(
        self, chat_id: int, photo_url: str, caption: str | None = None
    ) -> SendResult: ...

    def download_file(self, file_id: str, max_bytes: int) -> bytes: ...

    def set_my_commands(self, commands: list[dict]) -> bool: ...

    def answer_callback(self, callback_query_id: str, text: str | None = None) -> None: ...

    def set_webhook(self, url: str, secret_token: str) -> bool: ...

    def delete_webhook(self) -> bool: ...
