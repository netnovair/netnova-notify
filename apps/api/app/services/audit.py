from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.domain.audit_actions import action_label
from app.repositories.audit import AuditRepository


@dataclass(frozen=True)
class Actor:
    type: str
    id: uuid.UUID | None = None
    label: str | None = None


SYSTEM_ACTOR = Actor(type="system", label="سیستم")


class AuditService:
    @staticmethod
    def record(
        db: Session,
        *,
        actor: Actor,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        context: dict | None = None,
        now: datetime | None = None,
    ):
        return AuditRepository.add(
            db,
            actor_type=actor.type,
            actor_id=actor.id,
            actor_label=actor.label,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            context=context or {},
            now=now or utcnow(),
        )

    @staticmethod
    def label_for(action: str) -> str:
        return action_label(action)
