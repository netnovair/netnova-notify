from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.db.session import get_db
from app.repositories.audit import AuditRepository
from app.schemas.audit import AuditLogOut
from app.schemas.common import Page
from app.services.projects import ProjectService
from app.services.serializers import audit_out

router = APIRouter(prefix="/projects/{project_id}/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogOut])
def list_audit_logs(
    project_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> Page[AuditLogOut]:
    ProjectService.get(db, project_id)
    logs, total = AuditRepository.list_for_project(db, project_id, page=page, page_size=page_size)
    return Page[AuditLogOut](
        items=[audit_out(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )
