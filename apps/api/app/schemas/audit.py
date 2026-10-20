from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import ORMModel


class AuditLogOut(ORMModel):
    id: uuid.UUID
    actor_type: str
    actor_label: str | None
    action: str
    action_label: str | None = None
    entity_type: str
    entity_id: uuid.UUID | None
    project_id: uuid.UUID | None
    context: dict[str, Any]
    created_at: datetime
