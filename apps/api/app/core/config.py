"""Application settings loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def resolve_repo_root(module_path: Path) -> Path:
    """Locate the repository root for the optional development ``.env`` file.

    In the source checkout this file lives at ``<repo>/apps/api/app/core/config.py``,
    so the repository root is four levels up. The Docker image copies ``apps/api``
    to ``/app``, where the same file is ``/app/app/core/config.py`` and has only
    four parents - indexing ``parents[4]`` there raised ``IndexError`` and crashed
    the process at import time. Fall back to the topmost parent instead; the file
    is only a convenience path and pydantic tolerates a missing ``.env``.
    """
    parents = module_path.resolve().parents
    if len(parents) > 4:
        return parents[4]
    return parents[-1]


REPO_ROOT = resolve_repo_root(Path(__file__))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    secret_key: str = "development-only-secret-change-me"
    database_url: str = "postgresql+psycopg://netnova:netnova@localhost:5432/netnova"

    session_ttl_hours: int = Field(default=12, ge=1, le=24 * 30)
    cookie_secure: bool = False
    # Comma separated in the environment; pydantic-settings must not JSON-decode it.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_adapter: Literal["auto", "http", "mock"] = "auto"
    admin_telegram_chat_id: int | None = None

    # Additional notification providers. Empty credentials keep a channel
    # disabled; the panel never pretends a channel is active without them.
    bale_bot_token: str = ""
    bale_api_base: str = "https://tapi.bale.ai"
    eitaa_bot_token: str = ""
    eitaa_api_base: str = "https://eitaa.com/api"
    smsir_api_key: str = ""
    smsir_line_number: str = ""
    channel_http_timeout_seconds: float = Field(default=10.0, gt=0, le=60)

    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_name: str = "مدیر نت نووا"

    worker_poll_interval_seconds: float = Field(default=2.0, gt=0)
    worker_batch_size: int = Field(default=10, ge=1, le=100)
    worker_stale_seconds: int = Field(default=300, ge=30)
    job_max_attempts: int = Field(default=4, ge=1, le=20)
    job_backoff_base_seconds: int = Field(default=30, ge=1)

    tehran_timezone: str = "Asia/Tehran"
    payment_reminder_days_before: int = Field(default=3, ge=0, le=90)

    login_rate_limit: int = Field(default=10, ge=1)
    activation_rate_limit: int = Field(default=10, ge=1)

    api_internal_url: str = "http://127.0.0.1:8000"
    next_public_site_url: str = "http://localhost:3000"
    # Development-only: regex of extra trusted browser origins (e.g. a preview URL).
    # Ignored outside ENVIRONMENT=development.
    dev_preview_origin_regex: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("admin_telegram_chat_id", mode="before")
    @classmethod
    def _empty_int(cls, value: object) -> object:
        if value in ("", None):
            return None
        return value

    @field_validator(
        "telegram_bot_token",
        "telegram_webhook_secret",
        "bale_bot_token",
        "eitaa_bot_token",
        "smsir_api_key",
        "smsir_line_number",
        mode="after",
    )
    @classmethod
    def _strip_secret(cls, value: str) -> str:
        return value.strip()

    @property
    def allowed_origins(self) -> set[str]:
        """Normalized origins used for Origin header checks."""
        return {item.rstrip("/") for item in self.cors_origins}

    @property
    def telegram_mode(self) -> Literal["http", "mock"]:
        if self.telegram_adapter == "mock":
            return "mock"
        if self.telegram_adapter == "http":
            return "http"
        return "http" if self.telegram_bot_token else "mock"

    def validate_runtime(self) -> None:
        """Fail fast on unsafe production configuration."""
        problems: list[str] = []
        weak_secrets = {
            "development-only-secret-change-me",
            "replace-with-a-long-random-secret",
            "changeme",
            "",
        }
        if self.environment == "production":
            if self.secret_key in weak_secrets or len(self.secret_key) < 32:
                problems.append("SECRET_KEY must be a random value of at least 32 characters.")
            if not self.cookie_secure:
                problems.append("COOKIE_SECURE must be true in production (HTTPS required).")
            if self.telegram_mode == "http" and not self.telegram_webhook_secret:
                problems.append(
                    "TELEGRAM_WEBHOOK_SECRET is required when a real bot token is configured."
                )
            if "*" in self.cors_origins:
                problems.append("CORS_ORIGINS must not contain '*' in production.")
        if problems:
            raise RuntimeError("Invalid configuration: " + " ".join(problems))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
