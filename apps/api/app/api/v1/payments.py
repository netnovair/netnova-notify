from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.core.security import utcnow
from app.db.session import get_db
from app.domain.enums import PaymentStatus
from app.models.project import Project
from app.repositories.jobs import JobRepository
from app.repositories.payments import PaymentRepository
from app.schemas.common import Page
from app.schemas.payment import PaymentCreate, PaymentOut, PaymentUpdate
from app.services.payments import PaymentService
from app.services.projects import ProjectService
from app.services.serializers import payment_out

router = APIRouter(tags=["payments"])


def _payment_out(db: Session, payment) -> PaymentOut:
    project = db.get(Project, payment.project_id)
    job = JobRepository.next_payment_reminder(db, payment.id)
    return payment_out(
        payment,
        now=utcnow(),
        project_name=project.name if project else None,
        next_reminder_at=job.run_at if job else None,
    )


@router.get("/payments", response_model=Page[PaymentOut])
def list_all_payments(
    project_id: uuid.UUID | None = Query(default=None),
    status_filter: PaymentStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> Page[PaymentOut]:
    items, total = PaymentRepository.list_all(
        db,
        project_id=project_id,
        status=status_filter.value if status_filter else None,
        page=page,
        page_size=page_size,
    )
    now = utcnow()
    output = []
    for payment, project_name in items:
        job = JobRepository.next_payment_reminder(db, payment.id)
        output.append(
            payment_out(
                payment,
                now=now,
                project_name=project_name,
                next_reminder_at=job.run_at if job else None,
            )
        )
    return Page[PaymentOut](
        items=output,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/projects/{project_id}/payments", response_model=Page[PaymentOut])
def list_payments(
    project_id: uuid.UUID,
    status_filter: PaymentStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> Page[PaymentOut]:
    project = ProjectService.get(db, project_id)
    items, total = PaymentRepository.list_for_project(
        db,
        project_id,
        page=page,
        page_size=page_size,
        status=status_filter.value if status_filter else None,
    )
    now = utcnow()
    output = []
    for payment in items:
        job = JobRepository.next_payment_reminder(db, payment.id)
        output.append(
            payment_out(
                payment,
                now=now,
                project_name=project.name,
                next_reminder_at=job.run_at if job else None,
            )
        )
    return Page[PaymentOut](
        items=output,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/projects/{project_id}/payments", response_model=PaymentOut, status_code=201)
def create_payment(
    project_id: uuid.UUID,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> PaymentOut:
    project = ProjectService.get(db, project_id)
    payment = PaymentService.create(db, project=project, payload=payload, actor=ctx.actor)
    db.flush()
    return _payment_out(db, payment)


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> PaymentOut:
    return _payment_out(db, PaymentService.get(db, payment_id))


@router.patch("/payments/{payment_id}", response_model=PaymentOut)
def update_payment(
    payment_id: uuid.UUID,
    payload: PaymentUpdate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> PaymentOut:
    payment = PaymentService.get(db, payment_id)
    PaymentService.update(db, payment=payment, payload=payload, actor=ctx.actor)
    db.flush()
    return _payment_out(db, payment)


@router.post("/payments/{payment_id}/mark-paid", response_model=PaymentOut)
def mark_paid(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> PaymentOut:
    payment = PaymentService.get(db, payment_id)
    PaymentService.mark_paid(db, payment=payment, actor=ctx.actor)
    db.flush()
    return _payment_out(db, payment)


@router.post("/payments/{payment_id}/cancel", response_model=PaymentOut)
def cancel_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> PaymentOut:
    payment = PaymentService.get(db, payment_id)
    PaymentService.cancel(db, payment=payment, actor=ctx.actor)
    db.flush()
    return _payment_out(db, payment)
