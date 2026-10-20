"""Security primitives: password hashing, session tokens, license codes."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)

# Ambiguous characters (0/O, 1/I/L) are excluded to keep codes easy to type.
LICENSE_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "O0I1L")
LICENSE_GROUPS = 4
LICENSE_GROUP_LEN = 4


def utcnow() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def generate_license_code() -> str:
    groups = [
        "".join(secrets.choice(LICENSE_ALPHABET) for _ in range(LICENSE_GROUP_LEN))
        for _ in range(LICENSE_GROUPS)
    ]
    return "NN-" + "-".join(groups)


def normalize_license_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def hash_license_code(code: str, secret_key: str) -> str:
    """Keyed, deterministic hash so a database dump alone cannot verify guesses."""
    normalized = normalize_license_code(code)
    return hmac.new(
        secret_key.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def license_prefix(code: str) -> str:
    return code[:5]


def signed_payload(payload: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signed_payload(payload: str, signature: str, secret_key: str) -> bool:
    expected = signed_payload(payload, secret_key)
    return hmac.compare_digest(expected, signature)


def constant_time_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


# Readable alias used by session/CSRF checks.
compare_tokens = constant_time_compare


def session_expiry(hours: int) -> datetime:
    return utcnow() + timedelta(hours=hours)
