from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.core.security import utcnow
from app.db.session import get_db
from app.domain.enums import TicketStatus
from app.schemas.common import Page
from app.schemas.ticket import (
    TicketCreate,
    TicketDetail,
    TicketListItem,
    TicketReply,
    TicketStatusUpdate,
)
from app.services.projects import ProjectService
from app.services.serializers import ticket_detail, ticket_list_item
from app.services.tickets import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=Page[TicketListItem])
def list_tickets(
    ticket_status: TicketStatus | None = Query(default=None, alias="status"),
    project_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> Page[TicketListItem]:
    tickets, total = TicketService.list(
        db,
        project_id=project_id,
        status=ticket_status.value if ticket_status else None,
        page=page,
        page_size=page_size,
    )
    return Page[TicketListItem](
        items=[ticket_list_item(ticket, utcnow()) for ticket in tickets],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(
    ticket_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> TicketDetail:
    ticket = TicketService.get(db, ticket_id)
    TicketService.mark_read_by_admin(db, ticket)
    db.commit()
    return ticket_detail(ticket, utcnow())


@router.post("", response_model=TicketDetail, status_code=201)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> TicketDetail:
    project = ProjectService.get(db, payload.project_id)
    ticket = TicketService.create(
        db,
        project=project,
        subject=payload.subject,
        body=payload.body,
        created_by_type="admin",
        member=None,
        admin_id=ctx.admin.id,
        actor=ctx.actor,
        channel="web",
        priority=payload.priority,
    )
    db.commit()
    full = TicketService.get(db, ticket.id)
    return ticket_detail(full, utcnow())


@router.post("/{ticket_id}/reply", response_model=TicketDetail)
def reply_ticket(
    ticket_id: uuid.UUID,
    payload: TicketReply,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> TicketDetail:
    ticket = TicketService.get(db, ticket_id)
    TicketService.reply(
        db,
        ticket=ticket,
        body=payload.body,
        author_type="admin",
        admin_id=ctx.admin.id,
        actor=ctx.actor,
        channel="web",
    )
    db.commit()
    full = TicketService.get(db, ticket.id)
    return ticket_detail(full, utcnow())


@router.patch("/{ticket_id}/status", response_model=TicketDetail)
def set_ticket_status(
    ticket_id: uuid.UUID,
    payload: TicketStatusUpdate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> TicketDetail:
    ticket = TicketService.get(db, ticket_id)
    TicketService.set_status(db, ticket=ticket, status=payload.status.value, actor=ctx.actor)
    db.commit()
    full = TicketService.get(db, ticket.id)
    return ticket_detail(full, utcnow())
