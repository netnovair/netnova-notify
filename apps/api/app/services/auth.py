from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError, forbidden, unauthorized
from app.core.rate_limit import rate_limiter
from app.core.security import (
    compare_tokens,
    hash_password,
    hash_token,
    new_csrf_token,
    new_session_token,
    password_needs_rehash,
    session_expiry,
    utcnow,
    verify_password,
)
from app.models.admin import AdminSession, AdminUser
from app.repositories.users import AdminRepository, SessionRepository
from app.services.audit import Actor, AuditService

logger = logging.getLogger(__name__)

COOKIE_NAME = "nn_session"


class AuthService:
    @staticmethod
    def login(
        db: Session,
        *,
        email: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> tuple[str, str, AdminSession]:
        settings = get_settings()
        now = utcnow()
        limit_key = f"login:{ip_address or 'unknown'}"
        if not rate_limiter.allow(limit_key, settings.login_rate_limit, 60):
            raise ApiError(
                429,
                "rate_limited",
                "تعداد تلاش های ورود بیش از حد مجاز است. لطفا یک دقیقه بعد دوباره تلاش کنید.",
            )

        admin = AdminRepository.by_email(db, email)
        valid = admin is not None and verify_password(password, admin.password_hash)
        if not valid:
            AuditService.record(
                db,
                actor=Actor(type="system", label="ورود ناموفق"),
                action="auth.login_failed",
                entity_type="admin_user",
                entity_id=admin.id if admin else None,
                context={"email": email.lower()[:255], "ip": ip_address or "unknown"},
                now=now,
            )
            db.commit()
            raise ApiError(401, "invalid_credentials", "ایمیل یا رمز عبور صحیح نیست.")

        assert admin is not None
        if not admin.is_active:
            raise forbidden("حساب کاربری مدیر غیرفعال است.")

        if password_needs_rehash(admin.password_hash):
            admin.password_hash = hash_password(password)

        raw_token = new_session_token()
        csrf_token = new_csrf_token()
        expires_at = session_expiry(settings.session_ttl_hours)
        session = SessionRepository.create(
            db,
            admin=admin,
            token_hash=hash_token(raw_token),
            csrf_token=csrf_token,
            expires_at=expires_at,
            now=now,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        admin.last_login_at = now
        AuditService.record(
            db,
            actor=Actor(type="admin", id=admin.id, label=admin.display_name),
            action="auth.login",
            entity_type="admin_user",
            entity_id=admin.id,
            context={"ip": ip_address or "unknown"},
            now=now,
        )
        return raw_token, csrf_token, session

    @staticmethod
    def authenticate(db: Session, raw_token: str | None) -> tuple[AdminSession, AdminUser] | None:
        if not raw_token:
            return None
        session = SessionRepository.by_token_hash(db, hash_token(raw_token))
        if session is None:
            return None
        now = utcnow()
        if session.revoked_at is not None or session.expires_at <= now:
            return None
        admin = AdminRepository.by_id(db, session.admin_id)
        if admin is None or not admin.is_active:
            return None
        if now - session.last_seen_at > timedelta(minutes=5):
            session.last_seen_at = now
        return session, admin

    @staticmethod
    def require_session(db: Session, raw_token: str | None) -> tuple[AdminSession, AdminUser]:
        result = AuthService.authenticate(db, raw_token)
        if result is None:
            raise unauthorized()
        return result

    @staticmethod
    def verify_csrf(session: AdminSession, header_value: str | None) -> None:
        if not header_value or not compare_tokens(session.csrf_token, header_value):
            raise ApiError(
                403,
                "csrf_failed",
                "درخواست معتبر نیست. صفحه را دوباره بارگذاری کنید.",
            )

    @staticmethod
    def logout(db: Session, session: AdminSession, admin: AdminUser) -> None:
        now = utcnow()
        session.revoked_at = now
        AuditService.record(
            db,
            actor=Actor(type="admin", id=admin.id, label=admin.display_name),
            action="auth.logout",
            entity_type="admin_session",
            entity_id=session.id,
            now=now,
        )

    @staticmethod
    def admin_configured(db: Session) -> bool:
        return AdminRepository.count(db)

    @staticmethod
    def bootstrap_admin(db: Session) -> None:
        """Create the first admin from environment variables, only when none exists."""
        settings = get_settings()
        now = utcnow()
        if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
            if not AuthService.admin_configured(db):
                logger.warning(
                    "No admin account exists. Set BOOTSTRAP_ADMIN_EMAIL and "
                    "BOOTSTRAP_ADMIN_PASSWORD, then restart the API."
                )
            return
        if AuthService.admin_configured(db):
            return
        if len(settings.bootstrap_admin_password) < 10:
            logger.error("BOOTSTRAP_ADMIN_PASSWORD is too short; administrator was not created.")
            return
        admin = AdminUser(
            email=settings.bootstrap_admin_email.strip().lower(),
            password_hash=hash_password(settings.bootstrap_admin_password),
            display_name=settings.bootstrap_admin_name,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(admin)
        db.flush()
        AuditService.record(
            db,
            actor=Actor(type="system", label="راه اندازی اولیه"),
            action="system.bootstrap_admin_created",
            entity_type="admin_user",
            entity_id=admin.id,
            now=now,
        )
        db.commit()
        logger.info("Bootstrap administrator created: %s", admin.email)
