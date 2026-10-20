"""Concrete messaging providers.

Telegram reuses the mature adapter in ``app.adapters.telegram``. Bale and Eitaa
expose Telegram-compatible bot APIs, so one small HTTP adapter serves both. SMS.ir
uses its v1 JSON API and only supports plain text.

All providers are configured centrally: one bot/account per provider for the whole
agency. Per-project isolation comes from the license/membership layer, not from
separate credentials.
"""

from __future__ import annotations

import html
import logging
import re

import httpx

from app.adapters.messaging.base import (
    ChannelNotConfigured,
    DeliveryResult,
    PermanentChannelError,
    TemporaryChannelError,
    UnknownChannelError,
)
from app.adapters.telegram.base import (
    PermanentTelegramError,
    TelegramError,
    TemporaryTelegramError,
    UnknownTelegramError,
)
from app.adapters.telegram.factory import get_telegram_adapter
from app.core.config import Settings

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def plain_text(value: str) -> str:
    """Convert the HTML subset used by the bots into plain text (for SMS)."""
    text = _BREAK_RE.sub("\n", value)
    text = _TAG_RE.sub("", text)
    return html.unescape(text).strip()


class TelegramChannelAdapter:
    channel = "telegram"

    def __init__(self, settings: Settings, inner=None) -> None:
        # ``inner`` lets the worker inject a specific Telegram adapter (used by the
        # tests and by any future multi-bot setup) without bypassing this wrapper.
        self._inner = inner or get_telegram_adapter()

    @property
    def configured(self) -> bool:
        # Mock mode is a valid development configuration and stays visibly mock.
        return True

    @property
    def mode(self) -> str:
        return self._inner.mode

    def send(self, recipient: str, text: str, keyboard: dict | None = None) -> DeliveryResult:
        try:
            chat_id = int(recipient)
        except (TypeError, ValueError) as exc:
            raise PermanentChannelError("telegram recipient must be a numeric chat id") from exc
        try:
            result = self._inner.send_message(chat_id, text, keyboard)
        except TemporaryTelegramError as exc:
            raise TemporaryChannelError(str(exc), retry_after=exc.retry_after) from exc
        except UnknownTelegramError as exc:
            raise UnknownChannelError(str(exc)) from exc
        except PermanentTelegramError as exc:
            raise PermanentChannelError(str(exc)) from exc
        except TelegramError as exc:
            raise UnknownChannelError(str(exc)) from exc
        return DeliveryResult(
            message_id=str(result.message_id) if result.message_id is not None else None,
            is_mock=result.is_mock,
        )

    def send_plain(self, recipient: str, text: str) -> DeliveryResult:
        return self.send(recipient, text, None)


class _TelegramCompatibleHttpAdapter:
    """Shared implementation for Bale and Eitaa bot APIs."""

    channel = "generic"
    token_setting = ""
    base_setting = ""
    default_base = ""

    def __init__(self, settings: Settings) -> None:
        self._token = getattr(settings, self.token_setting).strip()
        self._base = (getattr(settings, self.base_setting) or self.default_base).rstrip("/")
        self._timeout = settings.channel_http_timeout_seconds
        self._client: httpx.Client | None = None

    @property
    def configured(self) -> bool:
        return bool(self._token)

    @property
    def mode(self) -> str:
        return "http" if self.configured else "unconfigured"

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base,
                timeout=httpx.Timeout(self._timeout, connect=5.0),
            )
        return self._client

    def send(self, recipient: str, text: str, keyboard: dict | None = None) -> DeliveryResult:
        if not self.configured:
            raise ChannelNotConfigured(self.channel)
        try:
            chat_id = int(recipient)
        except (TypeError, ValueError) as exc:
            raise PermanentChannelError(
                f"{self.channel} recipient must be a numeric chat id"
            ) from exc

        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if keyboard:
            payload["reply_markup"] = keyboard

        url = f"/bot{self._token}/sendMessage"
        try:
            response = self._http().post(url, json=payload)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise UnknownChannelError(
                f"{self.channel} transport failure: {type(exc).__name__}"
            ) from exc

        try:
            body = response.json()
        except ValueError:
            body = {}

        if response.status_code == 200 and body.get("ok"):
            result = body.get("result") or {}
            message_id = result.get("message_id")
            return DeliveryResult(message_id=str(message_id) if message_id is not None else None)

        description = str(body.get("description") or response.text[:200])
        retry_after = (body.get("parameters") or {}).get("retry_after")
        if response.status_code == 429 or response.status_code >= 500:
            raise TemporaryChannelError(
                f"{self.channel} temporary error {response.status_code}: {description}",
                retry_after=retry_after,
            )
        raise PermanentChannelError(
            f"{self.channel} rejected the request {response.status_code}: {description}"
        )

    def send_plain(self, recipient: str, text: str) -> DeliveryResult:
        return self.send(recipient, text, None)


class BaleAdapter(_TelegramCompatibleHttpAdapter):
    channel = "bale"
    token_setting = "bale_bot_token"
    base_setting = "bale_api_base"
    default_base = "https://tapi.bale.ai"


class EitaaAdapter(_TelegramCompatibleHttpAdapter):
    channel = "eitaa"
    token_setting = "eitaa_bot_token"
    base_setting = "eitaa_api_base"
    default_base = "https://eitaa.com/api"


class SmsIrAdapter:
    channel = "smsir"
    endpoint = "https://api.sms.ir/v1/send"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.smsir_api_key.strip()
        self._line = settings.smsir_line_number.strip()
        self._timeout = settings.channel_http_timeout_seconds
        self._client: httpx.Client | None = None

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._line)

    @property
    def mode(self) -> str:
        return "http" if self.configured else "unconfigured"

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def send(self, recipient: str, text: str, keyboard: dict | None = None) -> DeliveryResult:
        # SMS has no buttons; ignoring the keyboard would silently change the
        # meaning of a message, so callers must use send_plain instead.
        if keyboard:
            raise PermanentChannelError("smsir does not support keyboards")
        return self.send_plain(recipient, text)

    def send_plain(self, recipient: str, text: str) -> DeliveryResult:
        if not self.configured:
            raise ChannelNotConfigured(self.channel)
        mobile = re.sub(r"[\s-]", "", recipient)
        if not re.fullmatch(r"09\d{9}", mobile):
            raise PermanentChannelError("smsir recipient must look like 09xxxxxxxxx")

        payload = {
            "lineNumber": self._line,
            "messageText": plain_text(text)[:1000],
            "mobiles": [mobile],
            "sendDateTime": None,
        }
        try:
            response = self._http().post(
                self.endpoint,
                json=payload,
                headers={"x-api-key": self._api_key, "Accept": "application/json"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise UnknownChannelError(f"smsir transport failure: {type(exc).__name__}") from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise TemporaryChannelError(f"smsir temporary error {response.status_code}")
        if response.status_code >= 400:
            raise PermanentChannelError(f"smsir rejected the request {response.status_code}")

        try:
            body = response.json()
        except ValueError as exc:
            raise UnknownChannelError("smsir returned a non-JSON response") from exc
        if body.get("status") not in (1, "1", True):
            raise PermanentChannelError(str(body.get("message") or "smsir rejected the message"))
        data = body.get("data") or {}
        message_id = data.get("messageId") or data.get("packId")
        return DeliveryResult(message_id=str(message_id) if message_id is not None else None)
