from __future__ import annotations

import math
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.core.security import utcnow
from app.db.session import get_db
from app.domain.enums import LicenseStatus
from app.repositories.licenses import LicenseRepository
from app.schemas.common import Page
from app.schemas.license import LicenseCreate, LicenseCreated, LicenseOut, LicenseRevoke
from app.services.licenses import LicenseService
from app.services.projects import ProjectService
from app.services.serializers import license_out

router = APIRouter(tags=["licenses"])

DEFAULT_LICENSE_DAYS = 365


@router.get("/licenses", response_model=Page[LicenseOut])
def list_all_licenses(
    status_filter: LicenseStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> Page[LicenseOut]:
    LicenseService.expire_all_due(db)
    rows, total = LicenseRepository.list_all(
        db,
        status=status_filter.value if status_filter else None,
        page=page,
        page_size=page_size,
    )
    now = utcnow()
    return Page[LicenseOut](
        items=[license_out(row, now, project_name=name) for row, name in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/projects/{project_id}/licenses", response_model=LicenseCreated, status_code=201)
def issue_license(
    project_id: uuid.UUID,
    payload: LicenseCreate | None = None,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> LicenseCreated:
    project = ProjectService.get(db, project_id)
    now = utcnow()
    expires_at = payload.expires_at if payload else None
    if expires_at is None:
        expires_at = now + timedelta(days=DEFAULT_LICENSE_DAYS)
    license_row, code = LicenseService.issue(
        db,
        project=project,
        actor=ctx.actor,
        expires_at=expires_at,
        reason="manual_issue",
        commit=False,
    )
    out = license_out(license_row, now)
    return LicenseCreated(**out.model_dump(), code=code)


@router.post("/licenses/{license_id}/revoke", response_model=LicenseOut)
def revoke_license(
    license_id: uuid.UUID,
    payload: LicenseRevoke | None = None,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> LicenseOut:
    license_row = LicenseService.get(db, license_id)
    reason = (payload.reason if payload and payload.reason else "admin_revoked").strip()
    LicenseService.revoke(db, license_row=license_row, actor=ctx.actor, reason=reason)
    db.flush()
    db.refresh(license_row)
    return license_out(license_row, utcnow())


@router.get("/projects/{project_id}/license", response_model=LicenseOut | None)
def current_license(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> LicenseOut | None:
    ProjectService.get(db, project_id)
    live = LicenseRepository.live_for_project(db, project_id)
    if not live:
        return None
    return license_out(live[0], utcnow())
