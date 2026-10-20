"""Channel catalog + adapter factory.

Adding a provider:
1. implement ``ChannelAdapter`` in a new module;
2. add a ``ChannelDefinition`` below;
3. return the adapter from ``build_adapter``;
4. (optional) add credentials to ``Settings``.

Nothing else in the delivery pipeline changes: notifications, tickets and the
worker all talk to ``ChannelAdapter``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.adapters.messaging.base import ChannelAdapter, ChannelNotConfigured
from app.adapters.messaging.providers import (
    BaleAdapter,
    EitaaAdapter,
    SmsIrAdapter,
    TelegramChannelAdapter,
)
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChannelDefinition:
    key: str
    label: str
    description: str
    #: Where a recipient id comes from, shown in the admin UI.
    recipient_hint: str
    supports_keyboard: bool
    #: True while the integration has not been verified against a live account.
    beta: bool
    docs_url: str | None = None


CHANNELS: dict[str, ChannelDefinition] = {
    "telegram": ChannelDefinition(
        key="telegram",
        label="تلگرام",
        description="ربات مرکزی تلگرام؛ کارفرما با کد لایسنس به آن متصل می شود.",
        recipient_hint="شناسه عددی چت تلگرام (به صورت خودکار از ربات ثبت می شود)",
        supports_keyboard=True,
        beta=False,
        docs_url="https://core.telegram.org/bots/api",
    ),
    "bale": ChannelDefinition(
        key="bale",
        label="بله",
        description="ارسال از طریق API ربات بله. توکن ربات باید در محیط تنظیم شود.",
        recipient_hint="شناسه عددی چت بله",
        supports_keyboard=True,
        beta=True,
        docs_url="https://dev.bale.ai",
    ),
    "eitaa": ChannelDefinition(
        key="eitaa",
        label="ایتا",
        description="ارسال از طریق API ربات ایتا. توکن ربات باید در محیط تنظیم شود.",
        recipient_hint="شناسه عددی چت ایتا",
        supports_keyboard=True,
        beta=True,
        docs_url="https://eitaa.com",
    ),
    "smsir": ChannelDefinition(
        key="smsir",
        label="پیامک (sms.ir)",
        description="ارسال پیامک ساده از طریق سرویس sms.ir؛ بدون دکمه و منو.",
        recipient_hint="شماره موبایل با پیش شماره، مثل 09121234567",
        supports_keyboard=False,
        beta=True,
        docs_url="https://sms.ir",
    ),
}

CHANNEL_KEYS = tuple(CHANNELS)


def _build(settings: Settings, channel: str) -> ChannelAdapter:
    if channel == "telegram":
        return TelegramChannelAdapter(settings)
    if channel == "bale":
        return BaleAdapter(settings)
    if channel == "eitaa":
        return EitaaAdapter(settings)
    if channel == "smsir":
        return SmsIrAdapter(settings)
    raise ChannelNotConfigured(channel)


def get_channel_adapter(channel: str, settings: Settings | None = None) -> ChannelAdapter:
    settings = settings or get_settings()
    if channel not in CHANNELS:
        raise ChannelNotConfigured(channel)
    return _build(settings, channel)


def channel_state(channel: str, settings: Settings | None = None) -> dict:
    """Honest runtime state for the admin UI (never claims an unverified channel)."""
    settings = settings or get_settings()
    definition = CHANNELS[channel]
    try:
        adapter = get_channel_adapter(channel, settings)
        configured = adapter.configured
        mode = adapter.mode
    except Exception:  # noqa: BLE001 - a broken adapter must not break the catalog
        configured = False
        mode = "unconfigured"
    return {
        "key": definition.key,
        "label": definition.label,
        "description": definition.description,
        "recipient_hint": definition.recipient_hint,
        "supports_keyboard": definition.supports_keyboard,
        "beta": definition.beta,
        "docs_url": definition.docs_url,
        "configured": configured,
        "mode": mode,
    }


def channel_catalog(settings: Settings | None = None) -> list[dict]:
    return [channel_state(key, settings) for key in CHANNEL_KEYS]
