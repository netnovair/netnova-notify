"""Create clearly-marked demo data for local development.

* Only works when the Telegram adapter is in mock mode. Seeding can never send
  a real Telegram message to a synthetic chat id.
* Every created project has ``is_demo = true`` and is labeled in the admin UI.
* Demo license codes are printed once and use the same one-way storage as real
  licenses. They are demo credentials, not operational data.

Run from ``apps/api``:

    python -m scripts.seed_demo
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.project import Project
from app.models.telegram import TelegramUser
from app.repositories.licenses import MemberRepository
from app.repositories.users import TelegramUserRepository
from app.schemas.notification import NotificationCreate
from app.schemas.payment import PaymentCreate
from app.schemas.project import ProjectCreate
from app.services.audit import Actor
from app.services.catalog import CatalogService
from app.services.licenses import LicenseService
from app.services.notifications import NotificationService
from app.services.payments import PaymentService
from app.services.projects import ProjectService

SEED_ACTOR = Actor(type="system", label="داده نمایشی")


def _ensure_admin_hint(db) -> None:
    from app.repositories.users import AdminRepository

    admin = AdminRepository.by_email(db, get_settings().bootstrap_admin_email or "")
    if admin is None:
        print(
            "No bootstrap admin found. Set BOOTSTRAP_ADMIN_EMAIL and "
            "BOOTSTRAP_ADMIN_PASSWORD, start the API once, then re-run the seed."
        )


def _activate_demo_employer(db, *, project_id, code, telegram_id: int, name: str) -> None:
    if db.scalar(select(TelegramUser.id).where(TelegramUser.telegram_id == telegram_id)):
        print(f"Skipping synthetic employer {telegram_id}: already exists.")
        return
    user = TelegramUserRepository.upsert(
        db,
        telegram_id=telegram_id,
        username=f"demo_employer_{telegram_id}",
        first_name=name,
        last_name="نمایشی",
        now=utcnow(),
    )
    LicenseService.activate(db, code=code, telegram_user=user)
    member = MemberRepository.find(db, project_id=project_id, telegram_user_id=user.id)
    if member is not None:
        LicenseService.approve_member(db, member=member, actor=SEED_ACTOR)
    db.commit()


def main() -> int:
    setup_logging()
    settings = get_settings()
    if settings.telegram_mode == "http":
        print(
            "Refusing to seed demo data while a real Telegram bot is configured.\n"
            "Set TELEGRAM_ADAPTER=mock (and leave TELEGRAM_BOT_TOKEN empty) first."
        )
        return 1

    db = SessionLocal()
    try:
        existing = int(
            db.scalar(select(func.count(Project.id)).where(Project.is_demo.is_(True))) or 0
        )
        if existing:
            # The service catalog is operational configuration, not demo data, so it
            # is created independently of the demo projects and is safe to seed alone.
            seeded = CatalogService.seed_defaults(db, actor=SEED_ACTOR)
            db.commit()
            if seeded:
                print(f"Service catalog seeded ({seeded} categories).")
            print(f"Demo data already present ({existing} demo project(s)); nothing to do.")
            return 0

        seeded = CatalogService.seed_defaults(db, actor=SEED_ACTOR)
        db.commit()
        if seeded:
            print(f"Service catalog seeded ({seeded} categories).")

        now = utcnow()
        first, first_code = ProjectService.create(
            db,
            payload=ProjectCreate(
                name="فروشگاه آنلاین آرمان",
                client_name="آرمان تجارت",
                description="پروژه نمایشی برای بررسی گردش کار اطلاع رسانی.",
                slug="demo-arman-shop",
            ),
            actor=SEED_ACTOR,
        )
        first.is_demo = True
        db.flush()
        db.commit()

        second, second_code = ProjectService.create(
            db,
            payload=ProjectCreate(
                name="کمپین دیجیتال بهار",
                client_name="گروه بهار",
                description="پروژه نمایشی بدون کارفرمای متصل.",
                slug="demo-bahar-campaign",
            ),
            actor=SEED_ACTOR,
        )
        second.is_demo = True
        db.flush()
        db.commit()

        _activate_demo_employer(
            db,
            project_id=first.id,
            code=first_code,
            telegram_id=900000001,
            name="کارفرمای نمایشی",
        )

        payment = PaymentService.create(
            db,
            project=first,
            payload=PaymentCreate(
                title="پرداخت مرحله اول طراحی",
                amount_minor=8_500_000,
                currency="IRT",
                due_at=now + timedelta(days=5),
                notes="فقط برای نمایش وضعیت مالی؛ تراکنش واقعی نیست.",
            ),
            actor=SEED_ACTOR,
        )
        payment_row_status = payment.status
        db.commit()

        NotificationService.create(
            db,
            project=first,
            payload=NotificationCreate(
                title="تحویل نسخه اول طراحی",
                body="نسخه اول طراحی صفحات فروشگاه آماده بازبینی است.",
                scheduled_at=now + timedelta(days=1),
            ),
            actor=SEED_ACTOR,
        )
        db.commit()

        print("Demo data created. Projects are marked with the «نمایشی» badge.")
        print(f"  {first.name}: license {first_code}")
        print(f"  {second.name}: license {second_code}")
        print("  The demo employer uses synthetic Telegram id 900000001 (mock only).")
        print(f"  One open demo payment: {payment_row_status}.")
        print("Start the worker to process the queued welcome message in mock mode.")
        _ensure_admin_hint(db)
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"Seeding failed: {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
