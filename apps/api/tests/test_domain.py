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
        "performance",
        "progress",
    ]
    assert FEATURES[FeatureKey.ANNOUNCEMENTS].implemented is True
    assert FEATURES[FeatureKey.PERFORMANCE].implemented is False
    assert soon_message("performance").startswith("قابلیت «گزارش عملکرد»")
    assert soon_message("announcements") is None

    keyboard = project_menu_buttons(0, flags)
    callbacks = [button["callback_data"] for row in keyboard["inline_keyboard"] for button in row]
    assert callbacks[:3] == ["0:ann", "0:fin", "0:tickets"]
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
