"""Register or remove the Telegram webhook for the central bot.

The API never sets the webhook automatically: it must know its public HTTPS
URL. Run this after deployment:

    python -m scripts.set_webhook --url https://notify.example.com/api/v1/telegram/webhook

Requires TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET and TELEGRAM_ADAPTER=http.
"""

from __future__ import annotations

import argparse

from app.adapters.telegram.base import TelegramError
from app.adapters.telegram.factory import build_adapter
from app.core.config import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the Telegram webhook")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Public HTTPS webhook URL")
    group.add_argument("--delete", action="store_true", help="Delete the current webhook")
    args = parser.parse_args(argv)

    settings = get_settings()
    if settings.telegram_mode != "http":
        print("TELEGRAM_BOT_TOKEN is empty or the adapter is mock; nothing to register.")
        return 1
    if not settings.telegram_webhook_secret:
        print("TELEGRAM_WEBHOOK_SECRET must be set before registering the webhook.")
        return 1

    adapter = build_adapter(settings)
    try:
        if args.delete:
            adapter.delete_webhook()
            print("Webhook deleted.")
            return 0
        assert args.url
        if not args.url.startswith("https://"):
            print("Telegram requires an HTTPS webhook URL.")
            return 1
        adapter.set_webhook(args.url, settings.telegram_webhook_secret)
        print(f"Webhook registered: {args.url}")
        return 0
    except TelegramError as exc:
        print(f"Telegram error: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
