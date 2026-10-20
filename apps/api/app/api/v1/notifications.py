from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.db.session import get_db
from app.domain.enums import NotificationStatus
from app.models.project import Project
from app.repositories.notifications import NotificationRepository
from app.schemas.common import Page
from app.schemas.notification import (
    DeliveryOut,
    NotificationCreate,
    NotificationListItem,
    NotificationOut,
)
from app.services.notifications import NotificationService
from app.services.projects import ProjectService
from app.services.serializers import (
    notification_list_item,
    notification_out,
)

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=Page[NotificationListItem])
def list_all_notifications(
    project_id: uuid.UUID | None = Query(default=None),
    status_filter: NotificationStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> Page[NotificationListItem]:
    items, total = NotificationRepository.list_all(
        db,
        project_id=project_id,
        status=status_filter.value if status_filter else None,
        page=page,
        page_size=page_size,
    )
    project_ids = {item.project_id for item in items}
    names: dict[uuid.UUID, str] = {}
    if project_ids:
        rows = db.query(Project.id, Project.name).filter(Project.id.in_(project_ids)).all()
        names = {row[0]: row[1] for row in rows}
    return Page[NotificationListItem](
        items=[
            notification_list_item(
                item,
                project_name=names.get(item.project_id),
                is_mock=any(delivery.is_mock for delivery in item.deliveries),
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/projects/{project_id}/notifications", response_model=Page[NotificationListItem])
def list_project_notifications(
    project_id: uuid.UUID,
    status_filter: NotificationStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> Page[NotificationListItem]:
    project = ProjectService.get(db, project_id)
    items, total = NotificationRepository.list_for_project(
        db,
        project_id,
        page=page,
        page_size=page_size,
        status=status_filter.value if status_filter else None,
    )
    return Page[NotificationListItem](
        items=[
            notification_list_item(
                item,
                project_name=project.name,
                is_mock=any(delivery.is_mock for delivery in item.deliveries),
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post(
    "/projects/{project_id}/notifications", response_model=NotificationOut, status_code=201
)
def create_notification(
    project_id: uuid.UUID,
    payload: NotificationCreate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> NotificationOut:
    project = ProjectService.get(db, project_id)
    notification = NotificationService.create(db, project=project, payload=payload, actor=ctx.actor)
    db.refresh(notification)
    return notification_out(notification)


@router.get("/notifications/{notification_id}", response_model=NotificationOut)
def get_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> NotificationOut:
    return notification_out(NotificationService.get(db, notification_id))


@router.get("/notifications/{notification_id}/deliveries", response_model=list[DeliveryOut])
def list_deliveries(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> list[DeliveryOut]:
    notification = NotificationService.get(db, notification_id)
    return [
        DeliveryOut(
            id=delivery.id,
            channel=delivery.channel or "telegram",
            recipient=delivery.recipient or str(delivery.chat_id or ""),
            chat_id=delivery.chat_id,
            status=delivery.status,
            attempt_no=delivery.attempt_no,
            telegram_message_id=delivery.telegram_message_id,
            error=delivery.error,
            is_mock=delivery.is_mock,
            started_at=delivery.started_at,
            finished_at=delivery.finished_at,
        )
        for delivery in notification.deliveries
    ]


@router.post("/notifications/{notification_id}/send", response_model=NotificationOut)
def send_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> NotificationOut:
    notification = NotificationRepository.get(db, notification_id, lock=True)
    if notification is None:
        NotificationService.get(db, notification_id)  # raises a consistent 404
    assert notification is not None
    NotificationService.request_send(db, notification=notification, actor=ctx.actor)
    db.flush()
    db.refresh(notification)
    return notification_out(notification)


@router.post("/notifications/{notification_id}/cancel", response_model=NotificationOut)
def cancel_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> NotificationOut:
    notification = NotificationRepository.get(db, notification_id, lock=True)
    if notification is None:
        NotificationService.get(db, notification_id)
    assert notification is not None
    NotificationService.cancel(db, notification=notification, actor=ctx.actor)
    db.flush()
    db.refresh(notification)
    return notification_out(notification)
