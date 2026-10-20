"""Validation for files attached to support tickets.

Attachments live in PostgreSQL (``ticket_attachments``) instead of a disk or an
object store: free hosts have an ephemeral filesystem and an S3 bucket would add
a paid dependency. 5 MB per image and a hand-written signature check keep the
table bounded and stop non-image payloads (notably SVG, which can execute
script) from ever being stored or served.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENTS_PER_MESSAGE = 4
#: Telegram photos are jpeg; the panel may upload the rest. SVG is deliberately
#: absent because it is an executable document, not a safe image.
ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\u0600-\u06FF-]+")


class AttachmentError(ValueError):
    """The file is not an acceptable image attachment."""


@dataclass(frozen=True)
class AttachmentInput:
    data: bytes
    filename: str
    content_type: str | None = None


def sniff_image_type(data: bytes) -> str | None:
    """Return the real image type from magic bytes, or ``None``."""
    if len(data) < 12:
        return None
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def safe_filename(name: str, content_type: str, *, fallback: str = "attachment") -> str:
    """A short, printable name that keeps the extension matching the bytes."""
    base = unicodedata.normalize("NFKC", name or "").replace("\\", "/").rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    stem = _SAFE_NAME.sub("-", stem).strip("-._")[:80] or fallback
    return f"{stem}{ALLOWED_IMAGE_TYPES[content_type]}"


def validate_attachment(
    data: bytes, *, filename: str, declared_type: str | None
) -> tuple[str, str]:
    """Validate one upload and return ``(content_type, safe_filename)``."""
    if not data:
        raise AttachmentError("فایل ارسالی خالی است.")
    if len(data) > MAX_ATTACHMENT_BYTES:
        limit_mb = MAX_ATTACHMENT_BYTES // (1024 * 1024)
        raise AttachmentError(f"حجم هر تصویر حداکثر {limit_mb} مگابایت است.")
    content_type = sniff_image_type(data)
    if content_type is None:
        raise AttachmentError("فقط تصویر JPEG، PNG، WebP یا GIF پذیرفته می شود.")
    if declared_type and declared_type not in ALLOWED_IMAGE_TYPES:
        raise AttachmentError("نوع فایل اعلام شده با محتوای تصویر همخوان نیست.")
    return content_type, safe_filename(filename or "", content_type)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
