"""Payment rules and formatting (pure functions, covered by unit tests)."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.domain.enums import PaymentStatus

CURRENCY_LABELS = {
    "IRR": "ریال",
    "IRT": "تومان",
    "USD": "دلار",
    "EUR": "یورو",
}

# IRR/IRT have no minor unit; USD/EUR amounts are stored in cents.
MINOR_FACTOR = {"IRR": 1, "IRT": 1, "USD": 100, "EUR": 100}


def is_overdue(status: str, due_at: datetime, now: datetime) -> bool:
    return status == PaymentStatus.UNPAID.value and due_at < now


def can_edit(status: str) -> bool:
    return status == PaymentStatus.UNPAID.value


def format_amount(amount_minor: int, currency: str) -> str:
    label = CURRENCY_LABELS.get(currency, currency)
    factor = MINOR_FACTOR.get(currency, 1)
    value = amount_minor / factor
    number = f"{int(value):,}" if factor == 1 else f"{value:,.2f}"
    return f"{number} {label}"


def reminder_at(due_at: datetime, now: datetime, days_before: int) -> datetime | None:
    """When the single payment reminder should run.

    * due in the future and the reminder window has not passed -> due - N days
    * due in the future but the window already passed -> shortly after now
    * already due -> no automatic reminder (admin can send a financial
      notification explicitly; we do not silently spam overdue invoices)
    """
    if due_at <= now:
        return None
    scheduled = due_at - timedelta(days=days_before)
    if scheduled <= now:
        return now + timedelta(minutes=1)
    return scheduled
