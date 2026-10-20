"""License validity rules (pure functions, covered by unit tests)."""

from __future__ import annotations

from datetime import datetime

from app.domain.enums import LicenseStatus

LIVE_STATUSES = {LicenseStatus.PENDING.value, LicenseStatus.ACTIVE.value}


def effective_status(
    status: str,
    expires_at: datetime | None,
    now: datetime,
) -> str:
    """A license whose expiry passed is reported as expired even before the
    cleanup runs, so the admin never sees a stale 'active' badge."""
    if status in LIVE_STATUSES and expires_at is not None and expires_at <= now:
        return LicenseStatus.EXPIRED.value
    return status


def is_usable(
    status: str, expires_at: datetime | None, project_active: bool, now: datetime
) -> bool:
    if not project_active:
        return False
    if status not in LIVE_STATUSES:
        return False
    return not (expires_at is not None and expires_at <= now)


def should_auto_expire(status: str, expires_at: datetime | None, now: datetime) -> bool:
    return status in LIVE_STATUSES and expires_at is not None and expires_at <= now
