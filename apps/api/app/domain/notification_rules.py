"""Notification state-machine rules (pure functions, covered by unit tests)."""

from __future__ import annotations

from app.domain.enums import NotificationStatus

CANCELLABLE = {NotificationStatus.QUEUED.value, NotificationStatus.RETRY_WAIT.value}
RETRYABLE = {NotificationStatus.FAILED.value}


def can_cancel(status: str) -> bool:
    return status in CANCELLABLE


def can_retry(status: str) -> bool:
    return status in RETRYABLE


def can_schedule(status: str) -> bool:
    return status in {NotificationStatus.DRAFT.value, NotificationStatus.QUEUED.value}
