from __future__ import annotations

import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.core.security import hash_password, utcnow, verify_password
from app.models.admin import AdminUser
from app.services.audit import Actor, AuditService

MIN_PASSWORD_LENGTH = 10


class AdminService:
    """Admin accounts and password lifecycle.

    The agency is small, so there is a single admin role. Guards still matter:
    nobody can deactivate themselves and the last active admin cannot be
    deactivated, otherwise the panel would lock everyone out.
    """

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise conflict(f"رمز عبور باید حداقل {MIN_PASSWORD_LENGTH} کاراکتر باشد.")

    @staticmethod
    def list(db: Session) -> list[AdminUser]:
        return list(db.scalars(select(AdminUser).order_by(AdminUser.created_at)).all())

    @staticmethod
    def get(db: Session, admin_id: uuid.UUID) -> AdminUser:
        admin = db.get(AdminUser, admin_id)
        if admin is None:
            raise not_found("مدیر یافت نشد.")
        return admin

    @staticmethod
    def create(
        db: Session,
        *,
        email: str,
        display_name: str,
        password: str,
        actor: Actor,
    ) -> AdminUser:
        AdminService._validate_password(password)
        normalized = email.strip().lower()
        existing = db.scalar(select(AdminUser).where(AdminUser.email == normalized))
        if existing is not None:
            raise conflict("این ایمیل قبلا ثبت شده است.", code="email_taken")
        now = utcnow()
        admin = AdminUser(
            email=normalized,
            display_name=display_name.strip(),
            password_hash=hash_password(password),
            is_active=True,
            created_by=actor.id,
            last_password_change_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(admin)
        db.flush()
        AuditService.record(
            db,
            actor=actor,
            action="admin.created",
            entity_type="admin_user",
            entity_id=admin.id,
            context={"email": normalized},
            now=now,
        )
        return admin

    @staticmethod
    def update(
        db: Session,
        *,
        admin: AdminUser,
        display_name: str | None,
        is_active: bool | None,
        actor: Actor,
        current_admin_id: uuid.UUID,
    ) -> AdminUser:
        now = utcnow()
        changed: dict[str, object] = {}
        if display_name is not None and display_name.strip() != admin.display_name:
            admin.display_name = display_name.strip()
            changed["display_name"] = admin.display_name
        if is_active is not None and is_active != admin.is_active:
            if admin.id == current_admin_id and not is_active:
                raise conflict("نمی توانید حساب خودتان را غیرفعال کنید.")
            if not is_active:
                active_count = int(
                    db.scalar(select(func.count(AdminUser.id)).where(AdminUser.is_active.is_(True)))
                    or 0
                )
                if active_count <= 1:
                    raise conflict("حداقل یک مدیر فعال باید باقی بماند.")
            admin.is_active = is_active
            changed["is_active"] = is_active
        if changed:
            admin.updated_at = now
            AuditService.record(
                db,
                actor=actor,
                action="admin.updated",
                entity_type="admin_user",
                entity_id=admin.id,
                context={"changed": changed},
                now=now,
            )
            db.flush()
        return admin

    @staticmethod
    def change_password(
        db: Session,
        *,
        admin: AdminUser,
        current_password: str,
        new_password: str,
        actor: Actor,
        keep_session_id: uuid.UUID,
    ) -> None:
        if not verify_password(current_password, admin.password_hash):
            raise conflict("رمز عبور فعلی صحیح نیست.", code="invalid_current_password")
        AdminService._validate_password(new_password)
        if verify_password(new_password, admin.password_hash):
            raise conflict("رمز عبور جدید باید با رمز فعلی متفاوت باشد.")
        now = utcnow()
        admin.password_hash = hash_password(new_password)
        admin.last_password_change_at = now
        admin.updated_at = now
        # Every other session is revoked; the caller keeps the current one.
        from app.models.admin import AdminSession

        sessions = db.scalars(
            select(AdminSession).where(
                AdminSession.admin_id == admin.id,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > now,
                AdminSession.id != keep_session_id,
            )
        ).all()
        for session in sessions:
            session.revoked_at = now
        AuditService.record(
            db,
            actor=actor,
            action="admin.password_changed",
            entity_type="admin_user",
            entity_id=admin.id,
            now=now,
        )
        db.flush()

    @staticmethod
    def reset_password(
        db: Session,
        *,
        admin: AdminUser,
        actor: Actor,
    ) -> str:
        """Set a random temporary password and revoke all of that admin's sessions."""
        temporary = secrets.token_urlsafe(9)
        AdminService._validate_password(temporary)
        now = utcnow()
        admin.password_hash = hash_password(temporary)
        admin.last_password_change_at = now
        admin.updated_at = now
        from app.models.admin import AdminSession

        sessions = db.scalars(
            select(AdminSession).where(
                AdminSession.admin_id == admin.id,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > now,
            )
        ).all()
        for session in sessions:
            session.revoked_at = now
        AuditService.record(
            db,
            actor=actor,
            action="admin.password_reset",
            entity_type="admin_user",
            entity_id=admin.id,
            now=now,
        )
        db.flush()
        return temporary
