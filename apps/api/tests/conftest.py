from __future__ import annotations

import os
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-please-change-0123456789")
os.environ.setdefault("TELEGRAM_ADAPTER", "mock")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@netnova.ir")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "Test-Admin-Pass-123")
os.environ.setdefault("BOOTSTRAP_ADMIN_NAME", "مدیر تست")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")

if not os.environ.get("DATABASE_URL"):
    raise RuntimeError(
        "DATABASE_URL is required for the test suite, e.g. "
        "postgresql+psycopg://postgres@/netnova_test?host=/tmp/netnova-pgdata"
    )

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.rate_limit import rate_limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

settings = get_settings()

if settings.environment != "test":
    raise RuntimeError("Refusing to run the destructive test suite outside ENVIRONMENT=test.")
if "test" not in (make_url(settings.database_url).database or ""):
    raise RuntimeError("Refusing to run destructive tests: the database name must contain 'test'.")


def _reset_schema() -> None:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(text("GRANT ALL ON SCHEMA public TO public"))


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Prove that the migrations run against a completely empty database."""
    _reset_schema()
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_tables():
    rate_limiter.reset()
    yield
    names = ", ".join(f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables))
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    rate_limiter.reset()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_client(client: TestClient) -> TestClient:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.bootstrap_admin_email,
            "password": settings.bootstrap_admin_password,
        },
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


@pytest.fixture
def mock_adapter():
    from app.adapters.telegram.factory import get_telegram_adapter

    adapter = get_telegram_adapter()
    adapter.sent.clear()
    return adapter
