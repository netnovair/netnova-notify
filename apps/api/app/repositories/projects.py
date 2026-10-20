from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.license import License
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.project import Project, ProjectFeature
from app.models.telegram import ProjectMember


class ProjectRepository:
    @staticmethod
    def get(db: Session, project_id: uuid.UUID) -> Project | None:
        return db.scalar(
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.features),
                selectinload(Project.channels),
                selectinload(Project.members).selectinload(ProjectMember.telegram_user),
                selectinload(Project.members).selectinload(ProjectMember.channel_identities),
            )
        )

    @staticmethod
    def get_by_slug(db: Session, slug: str) -> Project | None:
        return db.scalar(select(Project).where(Project.slug == slug))

    @staticmethod
    def list(
        db: Session,
        *,
        search: str | None,
        status: str | None,
        page: int,
        page_size: int,
        include_archived: bool = False,
    ) -> tuple[list[Project], int]:
        query = select(Project)
        count_query = select(func.count(Project.id))
        filters = []
        if not include_archived:
            filters.append(Project.archived_at.is_(None))
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Project.name.ilike(term),
                    Project.client_name.ilike(term),
                    Project.slug.ilike(term),
                )
            )
        if status:
            filters.append(Project.status == status)
        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)
        total = int(db.scalar(count_query) or 0)
        items = list(
            db.scalars(
                query.options(
                    selectinload(Project.features),
                    selectinload(Project.channels),
                    selectinload(Project.members).selectinload(ProjectMember.telegram_user),
                    selectinload(Project.members).selectinload(ProjectMember.channel_identities),
                )
                .order_by(Project.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    @staticmethod
    def live_licenses(db: Session, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, License]:
        if not project_ids:
            return {}
        rows = db.scalars(
            select(License)
            .where(
                License.project_id.in_(project_ids),
                License.status.in_(["pending", "active"]),
            )
            .order_by(License.created_at.desc())
        ).all()
        result: dict[uuid.UUID, License] = {}
        for license_row in rows:
            result.setdefault(license_row.project_id, license_row)
        return result

    @staticmethod
    def notification_counts(db: Session, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not project_ids:
            return {}
        rows = db.execute(
            select(Notification.project_id, func.count(Notification.id))
            .where(Notification.project_id.in_(project_ids))
            .group_by(Notification.project_id)
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    @staticmethod
    def open_payment_counts(db: Session, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not project_ids:
            return {}
        rows = db.execute(
            select(Payment.project_id, func.count(Payment.id))
            .where(Payment.project_id.in_(project_ids), Payment.status == "unpaid")
            .group_by(Payment.project_id)
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    @staticmethod
    def sync_features(db: Session, project: Project, flags: dict[str, bool], now: datetime) -> None:
        existing = {feature.key: feature for feature in project.features}
        for key, enabled in flags.items():
            feature = existing.get(key)
            if feature is None:
                feature = ProjectFeature(project_id=project.id, key=key, enabled=enabled)
                db.add(feature)
                project.features.append(feature)
            else:
                feature.enabled = enabled
        project.updated_at = now
        db.flush()

    @staticmethod
    def feature_flags(project: Project) -> dict[str, bool]:
        return {feature.key: feature.enabled for feature in project.features}

    @staticmethod
    def demo_projects(db: Session) -> list[Project]:
        return list(db.scalars(select(Project).where(Project.is_demo.is_(True))).all())

    @staticmethod
    def active_members(db: Session, project_id: uuid.UUID) -> list[ProjectMember]:
        return list(
            db.scalars(
                select(ProjectMember)
                .where(ProjectMember.project_id == project_id, ProjectMember.status == "active")
                .options(
                    selectinload(ProjectMember.telegram_user),
                    selectinload(ProjectMember.channel_identities),
                )
                .order_by(ProjectMember.created_at)
            ).all()
        )
