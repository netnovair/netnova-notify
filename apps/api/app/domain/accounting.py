"""Pure accounting rules (no database access, unit-testable).

The vocabulary used by the panel and the bot:

* **invoice** - a row in ``payments``; ``amount_minor`` is the agreed amount;
* **debt** - the part of an invoice that has not been allocated yet;
* **receipt** - a payment claim uploaded by the employer (text and/or image);
* **credit** - money from an approved receipt that is not allocated to any
  invoice (an overpayment), kept on the project balance;
* **balance** - debt minus credit; zero means the project is settled.

All amounts are integer minor units, so no rounding error can appear in a total.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.enums import PaymentStatus


class InvoiceLike(Protocol):  # pragma: no cover - typing only
    id: object
    amount_minor: int
    amount_paid_minor: int
    status: str
    currency: str
    due_at: datetime


@dataclass(frozen=True)
class Allocation:
    payment_id: object
    amount_minor: int


@dataclass(frozen=True)
class Totals:
    currency: str
    debt_minor: int
    paid_minor: int
    overdue_minor: int
    credit_minor: int
    invoices_total: int
    invoices_open: int

    @property
    def balance_minor(self) -> int:
        return max(0, self.debt_minor - self.credit_minor)

    @property
    def settled(self) -> bool:
        """Settled means nothing is left to pay; an overpayment stays as credit."""
        return self.balance_minor == 0


def invoice_remaining(amount_minor: int, paid_minor: int) -> int:
    return max(0, int(amount_minor) - max(0, int(paid_minor)))


def invoice_status(amount_minor: int, paid_minor: int, current: str) -> str:
    """Status implied by the allocated amount (cancelled stays cancelled)."""
    if current == PaymentStatus.CANCELLED.value:
        return current
    paid = max(0, int(paid_minor))
    if paid >= int(amount_minor):
        return PaymentStatus.PAID.value
    if paid > 0:
        return PaymentStatus.PARTIALLY_PAID.value
    return PaymentStatus.UNPAID.value


def is_open_invoice(invoice: InvoiceLike) -> bool:
    return (
        invoice.status != PaymentStatus.CANCELLED.value
        and invoice_remaining(invoice.amount_minor, invoice.amount_paid_minor) > 0
    )


def auto_allocate(
    amount_minor: int, invoices: Iterable[InvoiceLike]
) -> tuple[list[Allocation], int]:
    """Apply ``amount_minor`` to open invoices, oldest due date first.

    Returns the allocations and the leftover (credit). An invoice is never
    overpaid: whatever remains after the last open invoice stays as credit.
    """
    remaining = max(0, int(amount_minor))
    allocations: list[Allocation] = []
    ordered = sorted(
        (invoice for invoice in invoices if is_open_invoice(invoice)),
        key=lambda invoice: (invoice.due_at, str(invoice.id)),
    )
    for invoice in ordered:
        if remaining <= 0:
            break
        if invoice.currency != (ordered[0].currency if ordered else invoice.currency):
            # Mixed currencies cannot be netted; the currency check is repeated
            # by the caller, this is only a guard for unsorted input.
            continue
        take = min(remaining, invoice_remaining(invoice.amount_minor, invoice.amount_paid_minor))
        if take <= 0:
            continue
        allocations.append(Allocation(payment_id=invoice.id, amount_minor=take))
        remaining -= take
    return allocations, remaining


def totals_for(
    invoices: Iterable[InvoiceLike],
    *,
    currency: str,
    credit_minor: int = 0,
    now: datetime,
) -> Totals:
    debt = paid = overdue = 0
    total = open_count = 0
    for invoice in invoices:
        if invoice.currency != currency:
            continue
        total += 1
        if invoice.status == PaymentStatus.CANCELLED.value:
            continue
        paid += max(0, invoice.amount_paid_minor)
        remaining = invoice_remaining(invoice.amount_minor, invoice.amount_paid_minor)
        if remaining > 0:
            open_count += 1
            debt += remaining
            if invoice.due_at < now:
                overdue += remaining
    return Totals(
        currency=currency,
        debt_minor=debt,
        paid_minor=paid,
        overdue_minor=overdue,
        credit_minor=max(0, credit_minor),
        invoices_total=total,
        invoices_open=open_count,
    )
