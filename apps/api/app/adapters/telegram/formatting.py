"""Formatting helpers for Telegram HTML messages and inline keyboards."""

from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

MAX_MESSAGE_LENGTH = 3900


def html_escape(value: str) -> str:
    return escape(value, quote=False)


def truncate(value: str, limit: int = MAX_MESSAGE_LENGTH) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 20].rstrip() + "\n\n(پیام کوتاه شد)"


def inline_keyboard(rows: list[list[tuple[str, str]]]) -> dict:
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row] for row in rows
        ]
    }


def menu_keyboard(items: list[tuple[str, str]]) -> dict:
    """Two buttons per row keeps the menu tappable on small screens."""
    rows: list[list[tuple[str, str]]] = []
    for index in range(0, len(items), 2):
        rows.append(items[index : index + 2])
    return inline_keyboard(rows)


def format_datetime(value: datetime, tz_name: str) -> str:
    localized = value.astimezone(ZoneInfo(tz_name))
    return localized.strftime("%Y-%m-%d %H:%M")


def format_date(value: datetime, tz_name: str) -> str:
    localized = value.astimezone(ZoneInfo(tz_name))
    return localized.strftime("%Y-%m-%d")
