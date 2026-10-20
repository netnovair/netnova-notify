from __future__ import annotations

from functools import lru_cache

from app.adapters.telegram.base import TelegramAdapter
from app.adapters.telegram.http import HttpTelegramAdapter
from app.adapters.telegram.mock import MockTelegramAdapter
from app.core.config import Settings, get_settings


def build_adapter(settings: Settings) -> TelegramAdapter:
    if settings.telegram_mode == "http":
        return HttpTelegramAdapter(settings.telegram_bot_token)
    return MockTelegramAdapter()


@lru_cache(maxsize=1)
def get_telegram_adapter() -> TelegramAdapter:
    return build_adapter(get_settings())
