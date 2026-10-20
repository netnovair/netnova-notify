from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.security import (
    generate_license_code,
    hash_license_code,
    normalize_license_code,
)
from app.domain.enums import FeatureKey
from app.domain.features import FEATURES, enabled_features, soon_message
from app.domain.jalali import format_jalali_date, gregorian_to_jalali
from app.domain.licenses import effective_status, is_usable, should_auto_expire
from app.domain.menu import project_menu_buttons
from app.domain.notification_rules import can_cancel, can_retry
from app.domain.payments import can_edit, format_amount, is_overdue, reminder_at

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def test_license_code_format_and_uniqueness() -> None:
    codes = {generate_license_code() for _ in range(50)}
    assert len(codes) == 50
    for code in codes:
        assert re.fullmatch(r"NN-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}", code)
        for forbidden in ("O", "0", "I", "1", "L"):
            assert forbidden not in code.replace("NN-", "")


def test_license_hash_is_keyed_deterministic_and_normalized() -> None:
    code = generate_license_code()
    first = hash_license_code(code, "secret-a")
    second = hash_license_code(code.lower().replace("-", " "), "secret-a")
    other = hash_license_code(code, "secret-b")
    assert first == second
    assert first != other
    assert len(first) == 64
    assert code not in first
    assert normalize_license_code(code).startswith("NN")


def test_license_effective_status_and_usability() -> None:
    future = NOW + timedelta(days=10)
    past = NOW - timedelta(seconds=1)
    assert effective_status("active", future, NOW) == "active"
    assert effective_status("active", past, NOW) == "expired"
    assert effective_status("revoked", past, NOW) == "revoked"
    assert is_usable("active", future, True, NOW) is True
    assert is_usable("active", future, False, NOW) is False
    assert is_usable("pending", future, True, NOW) is True
    assert is_usable("revoked", future, True, NOW) is False
    assert is_usable("active", past, True, NOW) is False
    assert should_auto_expire("active", past, NOW) is True
    assert should_auto_expire("revoked", past, NOW) is False


def test_payment_rules() -> None:
    assert reminder_at(NOW + timedelta(days=10), NOW, 3) == NOW + timedelta(days=7)
    assert reminder_at(NOW + timedelta(days=2), NOW, 3) == NOW + timedelta(minutes=1)
    assert reminder_at(NOW - timedelta(days=1), NOW, 3) is None
    assert is_overdue("unpaid", NOW - timedelta(days=1), NOW) is True
    assert is_overdue("paid", NOW - timedelta(days=1), NOW) is False
    assert is_overdue("unpaid", NOW + timedelta(days=1), NOW) is False
    assert can_edit("unpaid") is True
    assert can_edit("paid") is False
    assert format_amount(1_200_000, "IRT") == "1,200,000 تومان"
    assert format_amount(12_345, "USD") == "123.45 دلار"


def test_notification_status_rules() -> None:
    assert can_cancel("queued") is True
    assert can_cancel("retry_wait") is True
    assert can_cancel("sent") is False
    assert can_retry("failed") is True
    assert can_retry("queued") is False


def test_feature_registry_and_menu() -> None:
    flags = {key: definition.default_enabled for key, definition in FEATURES.items()}
    enabled = enabled_features(flags)
    assert [definition.key for definition in enabled] == [
        "announcements",
        "financial",
        "support",
        "advisor",
        "performance",
        "progress",
    ]
    assert FEATURES[FeatureKey.ANNOUNCEMENTS].implemented is True
    assert FEATURES[FeatureKey.PERFORMANCE].implemented is False
    assert soon_message("performance").startswith("قابلیت «گزارش عملکرد»")
    assert soon_message("announcements") is None

    keyboard = project_menu_buttons(0, flags)
    callbacks = [button["callback_data"] for row in keyboard["inline_keyboard"] for button in row]
    assert callbacks[:4] == ["0:ann", "0:fin", "0:tickets", "0:advice"]
    assert "0:soon:performance" in callbacks
    assert all(len(callback.encode("utf-8")) <= 64 for callback in callbacks)

    disabled_flags = {**flags, FeatureKey.FINANCIAL.value: False}
    assert FeatureKey.FINANCIAL not in [d.key for d in enabled_features(disabled_flags)]


def test_feature_plugin_registers_without_core_edits() -> None:
    """A new capability only needs its definition + handler; nothing else changes."""
    from app.features.base import (
        _REGISTRY,
        FeatureDefinition,
        enabled_features,
        find_by_action,
    )

    key = "invoice_demo"
    assert key not in _REGISTRY
    # Simulate a plugin module importing and registering itself.
    from app.features import register

    register(
        FeatureDefinition(
            key=key,
            label="فاکتور نمونه",
            description="تست پلاگین",
            implemented=False,
            default_enabled=False,
            order=99,
            action="invoice",
        )
    )
    try:
        assert find_by_action("invoice") is not None
        assert key in [definition.key for definition in enabled_features({key: True})]
        # A default-disabled plugin stays off for projects that never opted in.
        assert key not in [definition.key for definition in enabled_features({})]
    finally:
        _REGISTRY.pop(key, None)


def test_jalali_conversion_anchors() -> None:
    assert gregorian_to_jalali(2024, 3, 20) == (1403, 1, 1)
    assert gregorian_to_jalali(2026, 3, 21) == (1405, 1, 1)
    assert gregorian_to_jalali(2026, 10, 19) == (1405, 7, 27)
    tehran = ZoneInfo("Asia/Tehran")
    assert format_jalali_date(datetime(2026, 10, 19, 12, 0, tzinfo=tehran)) == "27 مهر 1405"


def test_auto_allocation_is_oldest_due_first_and_never_overpays() -> None:
    from dataclasses import dataclass
    from datetime import UTC, datetime, timedelta

    from app.domain.accounting import auto_allocate, totals_for

    @dataclass
    class Invoice:
        id: str
        amount_minor: int
        amount_paid_minor: int
        status: str
        currency: str
        due_at: datetime

    now = datetime(2026, 10, 20, tzinfo=UTC)
    later = Invoice("later", 3_000_000, 0, "unpaid", "IRT", now + timedelta(days=20))
    sooner = Invoice("sooner", 2_000_000, 0, "unpaid", "IRT", now + timedelta(days=5))
    paid = Invoice("paid", 1_000_000, 1_000_000, "paid", "IRT", now - timedelta(days=5))
    cancelled = Invoice("cancel", 9_000_000, 0, "cancelled", "IRT", now + timedelta(days=1))

    allocations, leftover = auto_allocate(4_000_000, [later, sooner, paid, cancelled])
    assert [(row.payment_id, row.amount_minor) for row in allocations] == [
        ("sooner", 2_000_000),
        ("later", 2_000_000),
    ]
    assert leftover == 0

    # Overpaying leaves the rest as credit instead of inflating an invoice.
    allocations, leftover = auto_allocate(6_000_000, [later, sooner])
    assert sum(row.amount_minor for row in allocations) == 5_000_000
    assert leftover == 1_000_000

    totals = totals_for([later, sooner, paid, cancelled], currency="IRT", now=now)
    assert totals.debt_minor == 5_000_000
    assert totals.paid_minor == 1_000_000
    assert totals.overdue_minor == 0
    assert totals.invoices_open == 2
    assert totals.settled is False

    # A credit larger than the debt means nothing is left to pay.
    overpaid = totals_for([sooner], currency="IRT", now=now, credit_minor=5_000_000)
    assert overpaid.balance_minor == 0
    assert overpaid.settled is True
    assert overpaid.credit_minor == 5_000_000


def test_invoice_status_follows_allocated_amount() -> None:
    from app.domain.accounting import invoice_remaining, invoice_status

    assert invoice_remaining(5_000_000, 2_000_000) == 3_000_000
    assert invoice_remaining(5_000_000, 7_000_000) == 0
    assert invoice_status(5_000_000, 0, "unpaid") == "unpaid"
    assert invoice_status(5_000_000, 2_000_000, "unpaid") == "partially_paid"
    assert invoice_status(5_000_000, 5_000_000, "partially_paid") == "paid"
    # A cancelled invoice never turns itself back on.
    assert invoice_status(5_000_000, 0, "cancelled") == "cancelled"


def test_telegram_markup_sanitizer_keeps_supported_tags_only() -> None:
    from app.domain.telegram_html import has_markup, plain_text, sanitize_telegram_html

    cleaned = sanitize_telegram_html(
        "<b>قرارداد</b> <i>جدید</i><script>alert(1)</script> "
        '<a href="https://example.com">لینک</a> <a href="javascript:evil()">بد</a> '
        "<blockquote expandable>نقل</blockquote> <code>NN-1234</code>"
    )
    assert "<b>قرارداد</b>" in cleaned
    assert "<i>جدید</i>" in cleaned
    assert "<script>" not in cleaned
    assert "&lt;script&gt;" in cleaned
    assert 'href="https://example.com"' in cleaned
    assert "javascript:" not in cleaned
    assert "<blockquote expandable>نقل</blockquote>" in cleaned
    assert "<code>NN-1234</code>" in cleaned
    assert plain_text(cleaned).startswith("قرارداد جدید")
    assert has_markup(cleaned) is True
    # Plain text stays byte-identical apart from escaping.
    assert sanitize_telegram_html("قیمت ۵۰۰ تومان & مالیات") == "قیمت ۵۰۰ تومان &amp; مالیات"


def test_template_rendering_escapes_values_and_keeps_markup() -> None:
    from app.domain.message_templates import render_template

    rendered = render_template(
        "<b>{project}</b>\nکد: <code>{license}</code>\n{unknown}",
        {"project": "فروشگاه <آرمان>", "license": "NN-AAAA-BBBB"},
    )
    assert "<b>فروشگاه &lt;آرمان&gt;</b>" in rendered
    assert "<code>NN-AAAA-BBBB</code>" in rendered
    # Unknown placeholders are left for the editor to notice, never silently dropped.
    assert "{unknown}" in rendered
