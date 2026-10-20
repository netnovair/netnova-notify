from __future__ import annotations

import logging
import sys

from app.core.config import get_settings

SENSITIVE_HINTS = (
    "bot_token",
    "password",
    "license_code",
    "secret",
)


class SensitiveDataFilter(logging.Filter):
    """Defense in depth: never let known secret field names reach log output.

    Application code already avoids logging secrets; this filter blocks
    accidental key/value logging of the most dangerous fields.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        for hint in SENSITIVE_HINTS:
            if hint in message:
                record.msg = "log record redacted (sensitive field name detected)"
                record.args = ()
                break
        return True


def setup_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s"))
    handler.addFilter(SensitiveDataFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    logging.getLogger("uvicorn.access").addFilter(SensitiveDataFilter())
