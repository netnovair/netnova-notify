from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


class AuditRepository:
    @staticmethod
    def add(
        db: Session,
        *,
        actor_type: str,
        actor_id: uuid.UUID | None,
        actor_label: str | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        project_id: uuid.UUID | None,
        context: dict,
        now,
    ) -> AuditLog:
        log = AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            actor_label=actor_label,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            context=context or {},
            created_at=now,
        )
        db.add(log)
        db.flush()
        return log

    @staticmethod
    def list_for_project(
        db: Session, project_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[AuditLog], int]:
        total = int(
            db.scalar(select(func.count(AuditLog.id)).where(AuditLog.project_id == project_id)) or 0
        )
        items = list(
            db.scalars(
                select(AuditLog)
                .where(AuditLog.project_id == project_id)
                .order_by(AuditLog.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    @staticmethod
    def recent(db: Session, limit: int = 8) -> list[AuditLog]:
        return list(
            db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
        )
