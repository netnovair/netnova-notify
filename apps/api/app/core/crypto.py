"""Reversible encryption for license codes at rest.

License codes are secrets: anyone holding one can connect a Telegram account to
a project. The database therefore stores a hash (for lookup) *and* a copy
encrypted with AES-GCM so the panel can show the code to the administrator when
a client asks for it.

The key lives in ``LICENSE_ENCRYPTION_KEY`` and must be different from
``SECRET_KEY``: rotating sessions must not make licenses unreadable, and a
database leak alone must not reveal codes.

Ciphertext layout: ``base64(nonce(12) || ciphertext || tag(16))``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
#: AES-GCM needs a 32-byte key; any longer passphrase is hashed into one.
KEY_BYTES = 32


class LicenseCryptoError(Exception):
    """The key is missing/invalid or the ciphertext cannot be authenticated."""


def _derive_key(raw: str) -> bytes:
    normalized = (raw or "").strip()
    if not normalized:
        raise LicenseCryptoError("LICENSE_ENCRYPTION_KEY is not configured")
    # Accept a 64-char hex key as-is and hash anything else, so a passphrase or
    # a base64 blob both work without a fragile format check.
    try:
        if len(normalized) == KEY_BYTES * 2:
            candidate = bytes.fromhex(normalized)
            if len(candidate) == KEY_BYTES:
                return candidate
    except ValueError:
        pass
    return hashlib.sha256(normalized.encode("utf-8")).digest()


def encryption_available(key: str) -> bool:
    return bool((key or "").strip())


def encrypt_code(code: str, *, key: str) -> str:
    if not code:
        raise LicenseCryptoError("empty code")
    aes = AESGCM(_derive_key(key))
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = aes.encrypt(nonce, code.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_code(token: str, *, key: str) -> str:
    if not token:
        raise LicenseCryptoError("empty ciphertext")
    try:
        payload = base64.b64decode(token.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise LicenseCryptoError("ciphertext is not valid base64") from exc
    if len(payload) <= NONCE_BYTES:
        raise LicenseCryptoError("ciphertext is truncated")
    nonce, ciphertext = payload[:NONCE_BYTES], payload[NONCE_BYTES:]
    try:
        plaintext = AESGCM(_derive_key(key)).decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise LicenseCryptoError("ciphertext failed authentication") from exc
    return plaintext.decode("utf-8")


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
