from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.license import License
from app.models.project import Project
from app.models.telegram import ProjectMember, TelegramUser


class LicenseRepository:
    @staticmethod
    def get(db: Session, license_id: uuid.UUID, *, lock: bool = False) -> License | None:
        query = select(License).where(License.id == license_id)
        if lock:
            query = query.with_for_update()
        return db.scalar(query)

    @staticmethod
    def by_code_hash(db: Session, code_hash: str, *, lock: bool = False) -> License | None:
        query = select(License).where(License.code_hash == code_hash)
        if lock:
            query = query.with_for_update()
        return db.scalar(query)

    @staticmethod
    def live_for_project(db: Session, project_id: uuid.UUID) -> list[License]:
        return list(
            db.scalars(
                select(License)
                .where(License.project_id == project_id, License.status.in_(["pending", "active"]))
                .order_by(License.created_at.desc())
            ).all()
        )

    @staticmethod
    def list_all(
        db: Session, *, status: str | None, page: int, page_size: int
    ) -> tuple[list[tuple[License, str]], int]:
        from sqlalchemy import func

        from app.models.project import Project as ProjectModel

        filters = []
        if status:
            filters.append(License.status == status)
        total = int(
            db.scalar(
                select(func.count(License.id))
                .join(ProjectModel, License.project_id == ProjectModel.id)
                .where(*filters)
            )
            or 0
        )
        rows = db.execute(
            select(License, ProjectModel.name)
            .join(ProjectModel, License.project_id == ProjectModel.id)
            .where(*filters)
            .order_by(License.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [(row[0], row[1]) for row in rows], total

    @staticmethod
    def live_due_for_expiry(db: Session, now) -> list[License]:
        return list(
            db.scalars(
                select(License).where(
                    License.status.in_(["pending", "active"]),
                    License.expires_at.is_not(None),
                    License.expires_at <= now,
                )
            ).all()
        )

    @staticmethod
    def list_for_project(db: Session, project_id: uuid.UUID) -> list[License]:
        return list(
            db.scalars(
                select(License)
                .where(License.project_id == project_id)
                .order_by(License.created_at.desc())
            ).all()
        )


class MemberRepository:
    @staticmethod
    def get(db: Session, member_id: uuid.UUID, *, lock: bool = False) -> ProjectMember | None:
        query = select(ProjectMember).where(ProjectMember.id == member_id)
        if lock:
            # PostgreSQL cannot lock the nullable side of an outer join, so the
            # eager load is applied only for read-only access.
            query = query.with_for_update()
        else:
            query = query.options(
                joinedload(ProjectMember.telegram_user),
                selectinload(ProjectMember.channel_identities),
            )
        return db.scalar(query)

    @staticmethod
    def find(
        db: Session,
        *,
        project_id: uuid.UUID,
        telegram_user_id: uuid.UUID,
    ) -> ProjectMember | None:
        return db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.telegram_user_id == telegram_user_id,
            )
        )

    @staticmethod
    def list_for_project(db: Session, project_id: uuid.UUID) -> list[ProjectMember]:
        return list(
            db.scalars(
                select(ProjectMember)
                .where(ProjectMember.project_id == project_id)
                .options(
                    joinedload(ProjectMember.telegram_user),
                    selectinload(ProjectMember.channel_identities),
                )
                .order_by(ProjectMember.created_at)
            ).all()
        )

    @staticmethod
    def active_memberships_for_user(
        db: Session, telegram_user_id: uuid.UUID
    ) -> list[ProjectMember]:
        return list(
            db.scalars(
                select(ProjectMember)
                .where(
                    ProjectMember.telegram_user_id == telegram_user_id,
                    ProjectMember.status == "active",
                )
                .options(
                    joinedload(ProjectMember.project).selectinload(Project.features),
                    joinedload(ProjectMember.license),
                )
                .order_by(ProjectMember.activated_at)
            ).all()
        )

    @staticmethod
    def memberships_for_user(db: Session, telegram_user_id: uuid.UUID) -> list[ProjectMember]:
        return list(
            db.scalars(
                select(ProjectMember)
                .where(ProjectMember.telegram_user_id == telegram_user_id)
                .options(
                    joinedload(ProjectMember.project).selectinload(Project.features),
                    joinedload(ProjectMember.license),
                )
                .order_by(
                    ProjectMember.activated_at.asc().nulls_last(),
                    ProjectMember.created_at.asc(),
                )
            ).all()
        )

    @staticmethod
    def has_active_for_project(db: Session, project_id: uuid.UUID) -> bool:
        return (
            db.scalar(
                select(ProjectMember.id)
                .where(ProjectMember.project_id == project_id, ProjectMember.status == "active")
                .limit(1)
            )
            is not None
        )


class TelegramUserLookup:
    @staticmethod
    def get(db: Session, telegram_user_id: uuid.UUID) -> TelegramUser | None:
        return db.get(TelegramUser, telegram_user_id)

    @staticmethod
    def touch(db: Session, user: TelegramUser, now: datetime) -> None:
        user.updated_at = now
