from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import NotificationStatus
from app.models.notification import DeliveryAttempt, Notification


class NotificationRepository:
    @staticmethod
    def get(db: Session, notification_id: uuid.UUID, *, lock: bool = False) -> Notification | None:
        query = (
            select(Notification)
            .where(Notification.id == notification_id)
            .options(selectinload(Notification.deliveries))
        )
        if lock:
            query = query.with_for_update()
        return db.scalar(query)

    @staticmethod
    def count_for_project(db: Session, project_id: uuid.UUID) -> int:
        return int(
            db.scalar(
                select(func.count(Notification.id)).where(Notification.project_id == project_id)
            )
            or 0
        )

    @staticmethod
    def list_for_project(
        db: Session,
        project_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
    ) -> tuple[list[Notification], int]:
        filters = [Notification.project_id == project_id]
        if status:
            filters.append(Notification.status == status)
        total = int(db.scalar(select(func.count(Notification.id)).where(*filters)) or 0)
        items = list(
            db.scalars(
                select(Notification)
                .where(*filters)
                .options(selectinload(Notification.deliveries))
                .order_by(Notification.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    @staticmethod
    def list_all(
        db: Session,
        *,
        project_id: uuid.UUID | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Notification], int]:
        filters = []
        if project_id:
            filters.append(Notification.project_id == project_id)
        if status:
            filters.append(Notification.status == status)
        total = int(db.scalar(select(func.count(Notification.id)).where(*filters)) or 0)
        items = list(
            db.scalars(
                select(Notification)
                .where(*filters)
                .options(selectinload(Notification.deliveries))
                .order_by(Notification.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    @staticmethod
    def recent_sent(db: Session, project_id: uuid.UUID, limit: int = 5) -> list[Notification]:
        return list(
            db.scalars(
                select(Notification)
                .where(
                    Notification.project_id == project_id,
                    Notification.status == NotificationStatus.SENT,
                )
                .order_by(Notification.sent_at.desc())
                .limit(limit)
            ).all()
        )

    @staticmethod
    def count_by_status(
        db: Session, statuses: list[str], project_id: uuid.UUID | None = None
    ) -> int:
        query = select(func.count(Notification.id)).where(Notification.status.in_(statuses))
        if project_id:
            query = query.where(Notification.project_id == project_id)
        return int(db.scalar(query) or 0)

    @staticmethod
    def recent_deliveries(db: Session, limit: int = 10) -> list[DeliveryAttempt]:
        return list(
            db.scalars(
                select(DeliveryAttempt).order_by(DeliveryAttempt.created_at.desc()).limit(limit)
            ).all()
        )
