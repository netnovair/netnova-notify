from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import AdminSession, AdminUser
from app.models.telegram import TelegramUser


class AdminRepository:
    @staticmethod
    def by_email(db: Session, email: str) -> AdminUser | None:
        return db.scalar(select(AdminUser).where(AdminUser.email == email.strip().lower()))

    @staticmethod
    def by_id(db: Session, admin_id: uuid.UUID) -> AdminUser | None:
        return db.get(AdminUser, admin_id)

    @staticmethod
    def count(db: Session) -> int:
        return int(db.scalar(select(AdminUser.id).limit(1)) is not None)


class SessionRepository:
    @staticmethod
    def by_token_hash(db: Session, token_hash: str) -> AdminSession | None:
        return db.scalar(select(AdminSession).where(AdminSession.token_hash == token_hash))

    @staticmethod
    def create(
        db: Session,
        *,
        admin: AdminUser,
        token_hash: str,
        csrf_token: str,
        expires_at: datetime,
        now: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AdminSession:
        session = AdminSession(
            admin_id=admin.id,
            token_hash=token_hash,
            csrf_token=csrf_token,
            expires_at=expires_at,
            created_at=now,
            last_seen_at=now,
            user_agent=(user_agent or "")[:300] or None,
            ip_address=ip_address,
        )
        db.add(session)
        db.flush()
        return session

    @staticmethod
    def revoke_all_for_admin(db: Session, admin_id: uuid.UUID, now: datetime) -> None:
        sessions = db.scalars(
            select(AdminSession).where(
                AdminSession.admin_id == admin_id,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > now,
            )
        ).all()
        for session in sessions:
            session.revoked_at = now


class TelegramUserRepository:
    @staticmethod
    def by_telegram_id(db: Session, telegram_id: int) -> TelegramUser | None:
        return db.scalar(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))

    @staticmethod
    def upsert(
        db: Session,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        now: datetime,
    ) -> TelegramUser:
        user = TelegramUserRepository.by_telegram_id(db, telegram_id)
        if user is None:
            user = TelegramUser(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                created_at=now,
                updated_at=now,
            )
            db.add(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.updated_at = now
        db.flush()
        return user
