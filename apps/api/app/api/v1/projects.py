from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.core.errors import ApiError
from app.core.security import utcnow
from app.db.session import get_db
from app.domain.enums import ProjectStatus
from app.repositories.licenses import LicenseRepository
from app.repositories.notifications import NotificationRepository
from app.repositories.payments import PaymentRepository
from app.repositories.projects import ProjectRepository
from app.repositories.tickets import TicketRepository
from app.schemas.common import Page
from app.schemas.license import LicenseOut
from app.schemas.project import (
    ProjectChannelUpdate,
    ProjectCreate,
    ProjectCreated,
    ProjectFeaturesUpdate,
    ProjectListItem,
    ProjectOut,
    ProjectUpdate,
)
from app.services.licenses import LicenseService
from app.services.projects import (
    ProjectChannelService,
    ProjectLifecycleService,
    ProjectService,
)
from app.services.projects import (
    purge_demo_projects as purge_demo_projects_data,
)
from app.services.serializers import license_out, project_list_item, project_out

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_detail(db: Session, project_id: uuid.UUID) -> ProjectOut:
    project = ProjectService.get(db, project_id)
    LicenseService.enforce_expiry_for_project(db, project_id)
    license_row = LicenseRepository.live_for_project(db, project_id)
    now = utcnow()
    return project_out(
        project,
        license_row=license_row[0] if license_row else None,
        open_payments_count=len(PaymentRepository.open_payments_for_project(db, project_id)),
        notifications_count=NotificationRepository.count_for_project(db, project_id),
        now=now,
    )


@router.get("", response_model=Page[ProjectListItem])
def list_projects(
    search: str | None = Query(default=None, max_length=120),
    project_status: ProjectStatus | None = Query(default=None, alias="status"),
    include_archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> Page[ProjectListItem]:
    projects, total = ProjectService.list(
        db,
        search=search,
        status=project_status.value if project_status else None,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )
    ids = [project.id for project in projects]
    licenses = ProjectRepository.live_licenses(db, ids)
    notification_counts = ProjectRepository.notification_counts(db, ids)
    payment_counts = ProjectRepository.open_payment_counts(db, ids)
    ticket_counts = TicketRepository.unread_counts(db, ids)
    now = utcnow()
    return Page[ProjectListItem](
        items=[
            project_list_item(
                project,
                license_row=licenses.get(project.id),
                open_payments_count=payment_counts.get(project.id, 0),
                notifications_count=notification_counts.get(project.id, 0),
                open_tickets=ticket_counts.get(project.id, 0),
                now=now,
            )
            for project in projects
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=ProjectCreated, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ProjectCreated:
    project, license_code = ProjectService.create(db, payload=payload, actor=ctx.actor)
    detail = _project_detail(db, project.id)
    return ProjectCreated(**detail.model_dump(), license_code=license_code)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> ProjectOut:
    return _project_detail(db, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ProjectOut:
    project = ProjectService.get(db, project_id)
    ProjectService.update(db, project=project, payload=payload, actor=ctx.actor)
    return _project_detail(db, project_id)


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ProjectOut:
    project = ProjectService.get(db, project_id)
    ProjectLifecycleService.archive(db, project=project, actor=ctx.actor)
    db.commit()
    return _project_detail(db, project_id)


@router.post("/{project_id}/restore", response_model=ProjectOut)
def restore_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ProjectOut:
    project = ProjectService.get(db, project_id)
    ProjectLifecycleService.restore(db, project=project, actor=ctx.actor)
    db.commit()
    return _project_detail(db, project_id)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: uuid.UUID,
    confirm: str = Query(..., max_length=160),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> None:
    """Permanent deletion. ``confirm`` must repeat the project name exactly."""
    project = ProjectService.get(db, project_id)
    if confirm.strip() != project.name:
        raise ApiError(
            422,
            "confirmation_mismatch",
            "برای حذف قطعی، نام پروژه را دقیقا وارد کنید.",
        )
    ProjectLifecycleService.delete(db, project=project, actor=ctx.actor)
    db.commit()


@router.get("/{project_id}/features")
def list_project_features(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
):
    project = ProjectService.get(db, project_id)
    detail = _project_detail(db, project_id)
    return {"project_id": project.id, "features": detail.features}


@router.put("/{project_id}/features", response_model=ProjectOut)
def update_project_features(
    project_id: uuid.UUID,
    payload: ProjectFeaturesUpdate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ProjectOut:
    project = ProjectService.get(db, project_id)
    ProjectService.update(
        db,
        project=project,
        payload=ProjectUpdate(features=payload.features),
        actor=ctx.actor,
    )
    db.commit()
    return _project_detail(db, project_id)


@router.put("/{project_id}/channels/{channel}", response_model=ProjectOut)
def update_project_channel(
    project_id: uuid.UUID,
    channel: str,
    payload: ProjectChannelUpdate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ProjectOut:
    project = ProjectService.get(db, project_id)
    ProjectChannelService.update(
        db, project=project, channel=channel, payload=payload, actor=ctx.actor
    )
    db.commit()
    return _project_detail(db, project_id)


@router.post("/demo-purge")
def purge_demo_projects(
    confirm: str = Query(..., max_length=40),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> dict:
    """Delete all demo-flagged projects. ``confirm`` must be the word DEMO."""
    if confirm.strip().upper() != "DEMO":
        raise ApiError(422, "confirmation_mismatch", "برای حذف داده های نمایشی، عبارت DEMO را وارد کنید.")
    result = purge_demo_projects_data(db, actor=ctx.actor)
    db.commit()
    return result


@router.get("/{project_id}/licenses")
def list_licenses(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> list[LicenseOut]:
    ProjectService.get(db, project_id)
    licenses = LicenseService.list_for_project(db, project_id)
    now = utcnow()
    return [license_out(row, now) for row in licenses]
