from __future__ import annotations

import pytest

from app.core.config import Settings


def test_comma_separated_cors_origins_are_accepted(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example.com, https://b.example.com")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]
    assert settings.allowed_origins == {"https://a.example.com", "https://b.example.com"}


def test_origin_normalization_strips_trailing_slash(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://notify.example.com/")
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == {"https://notify.example.com"}


def test_production_rejects_placeholder_secret(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "development-only-secret-change-me")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "x" * 32)
    settings = Settings(_env_file=None)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        settings.validate_runtime()


def test_production_requires_secure_cookies(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 48)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "b" * 32)
    monkeypatch.setenv("COOKIE_SECURE", "false")
    settings = Settings(_env_file=None)
    with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
        settings.validate_runtime()


def test_production_rejects_wildcard_origin(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 48)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "b" * 32)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    settings = Settings(_env_file=None)
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        settings.validate_runtime()


def test_development_does_not_require_production_hardening(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    settings = Settings(_env_file=None)
    settings.validate_runtime()
