from __future__ import annotations

import math
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.core.errors import ApiError, conflict, not_found
from app.core.rate_limit import rate_limiter
from app.core.security import utcnow
from app.db.session import get_db
from app.domain.enums import LicenseStatus
from app.repositories.licenses import LicenseRepository, MemberRepository
from app.schemas.common import Page
from app.schemas.license import (
    LicenseCodeOut,
    LicenseCreate,
    LicenseCreated,
    LicenseDeliver,
    LicenseOut,
    LicenseReissue,
    LicenseRevoke,
)
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


@router.get("/licenses/{license_id}/code", response_model=LicenseCodeOut)
def reveal_license_code(
    license_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> LicenseCodeOut:
    """Show the full code to an administrator (audited and rate limited).

    List responses keep exposing only the prefix; the code is fetched on demand
    so it never ends up in a cached list or a log line.
    """
    if not rate_limiter.allow(f"license-code:{ctx.admin.id}", limit=10, window_seconds=60):
        raise ApiError(429, "rate_limited", "تعداد درخواست های نمایش کد زیاد است. کمی صبر کنید.")
    license_row = LicenseService.get(db, license_id)
    code = LicenseService.reveal_code(db, license_row=license_row, actor=ctx.actor)
    db.commit()
    return LicenseCodeOut(id=license_row.id, code=code, code_prefix=license_row.code_prefix)


@router.post("/licenses/{license_id}/reissue", response_model=LicenseCreated, status_code=201)
def reissue_license(
    license_id: uuid.UUID,
    payload: LicenseReissue | None = None,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> LicenseCreated:
    """Replace a hash-only license: the old code stops working immediately."""
    license_row = LicenseService.get(db, license_id)
    new_license, code = LicenseService.reissue(
        db,
        license_row=license_row,
        actor=ctx.actor,
        expires_at=payload.expires_at if payload else None,
    )
    db.commit()
    out = license_out(new_license, utcnow())
    return LicenseCreated(**out.model_dump(), code=code)


@router.post("/licenses/{license_id}/deliver", response_model=LicenseOut)
def deliver_license(
    license_id: uuid.UUID,
    payload: LicenseDeliver | None = None,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> LicenseOut:
    """Queue a private delivery of the code to the employer's Telegram chat."""
    license_row = LicenseService.get(db, license_id)
    # Checked before the member lookup so a revoked/expired licence always
    # answers with the real reason instead of "no employer found".
    if LicenseService.effective(license_row) in {
        LicenseStatus.REVOKED.value,
        LicenseStatus.EXPIRED.value,
    }:
        raise conflict(
            "این لایسنس لغو یا منقضی شده است؛ ارسال کد برای کارفرما انجام نمی شود.",
            code="license_not_active",
        )
    members = [
        member
        for member in MemberRepository.list_for_project(db, license_row.project_id)
        if member.status == "active"
    ]
    if payload and payload.member_id is not None:
        members = [member for member in members if member.id == payload.member_id]
    if not members:
        raise not_found("کارفرمای تاییدشده ای برای این پروژه یافت نشد.")
    LicenseService.enqueue_delivery(db, license_row=license_row, member=members[0], actor=ctx.actor)
    db.commit()
    return license_out(license_row, utcnow())
