"""Gregorian -> Jalali date conversion for Telegram messages.

The admin PWA uses the browser's Intl API; the bot needs a small server-side
equivalent. Algorithm: jalaali-js (public domain), verified for Nowruz anchors
in the unit tests.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

MONTH_NAMES = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]

_GREGORIAN_DAYS_IN_MONTH = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    if not (1 <= gm <= 12 and 1 <= gd <= 31):
        raise ValueError("Invalid Gregorian date")
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        - 80
        + gd
        + _GREGORIAN_DAYS_IN_MONTH[gm - 1]
    )
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def format_jalali_date(value: datetime, tz_name: str = "Asia/Tehran") -> str:
    local = value.astimezone(ZoneInfo(tz_name))
    jy, jm, jd = gregorian_to_jalali(local.year, local.month, local.day)
    return f"{jd} {MONTH_NAMES[jm - 1]} {jy}"


def format_jalali_datetime(value: datetime, tz_name: str = "Asia/Tehran") -> str:
    local = value.astimezone(ZoneInfo(tz_name))
    jy, jm, jd = gregorian_to_jalali(local.year, local.month, local.day)
    return f"{jd} {MONTH_NAMES[jm - 1]} {jy} - {local.strftime('%H:%M')}"
