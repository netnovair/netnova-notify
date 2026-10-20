from __future__ import annotations

import math
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.core.errors import bad_request, not_found
from app.core.security import utcnow
from app.db.session import get_db
from app.domain.attachments import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS_PER_MESSAGE,
    AttachmentInput,
)
from app.domain.enums import TicketStatus
from app.models.ticket import TicketAttachment
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


@router.get("/attachments/{attachment_id}")
def download_ticket_attachment(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> Response:
    """Serve one stored image to an authenticated admin.

    The bytes are always returned with ``nosniff`` and a private cache policy;
    the filename is RFC 5987 encoded so Persian names survive the header.
    """
    attachment = db.get(TicketAttachment, attachment_id)
    if attachment is None:
        raise not_found("تصویر پیوست یافت نشد.")
    return Response(
        content=attachment.data,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(attachment.filename)}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{ticket_id}/attachments", response_model=TicketDetail)
async def reply_ticket_with_images(
    ticket_id: uuid.UUID,
    body: str = Form(default=""),
    files: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> TicketDetail:
    """Reply to a ticket with up to four images (multipart/form-data)."""
    uploads = files or []
    if not uploads:
        raise bad_request("حداقل یک تصویر انتخاب کنید.", code="no_attachment")
    if len(uploads) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise bad_request(
            f"حداکثر {MAX_ATTACHMENTS_PER_MESSAGE} تصویر در هر پیام ارسال کنید.",
            code="too_many_attachments",
        )
    ticket = TicketService.get(db, ticket_id)
    drafts = [
        AttachmentInput(
            data=await upload.read(MAX_ATTACHMENT_BYTES + 1),
            filename=upload.filename or "image",
            content_type=upload.content_type,
        )
        for upload in uploads
    ]
    TicketService.reply(
        db,
        ticket=ticket,
        body=body,
        author_type="admin",
        admin_id=ctx.admin.id,
        actor=ctx.actor,
        channel="web",
        attachments=drafts,
    )
    db.commit()
    full = TicketService.get(db, ticket.id)
    return ticket_detail(full, utcnow())


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
