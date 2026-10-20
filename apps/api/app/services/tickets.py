from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import conflict, not_found
from app.core.security import utcnow
from app.domain.enums import JobKind, TicketAuthorType, TicketStatus
from app.models.project import Project
from app.models.telegram import ProjectMember
from app.models.ticket import Ticket, TicketMessage
from app.repositories.jobs import JobRepository
from app.services.audit import Actor, AuditService

SUBJECT_LIMIT = 200
BODY_LIMIT = 4000


class TicketService:
    """Two-way support threads between the agency and one project employer.

    Status semantics:
    * ``open`` - just created, nobody answered yet;
    * ``pending_admin`` - the employer is waiting for the agency;
    * ``pending_employer`` - the agency replied and waits for the employer;
    * ``closed`` - resolved; a new message reopens the thread.
    """

    @staticmethod
    def _clean(value: str, *, limit: int, field: str) -> str:
        text = (value or "").strip()
        if not text:
            raise conflict(f"{field} نمی تواند خالی باشد.")
        if len(text) > limit:
            raise conflict(f"{field} بیش از حد طولانی است (حداکثر {limit} کاراکتر).")
        return text

    @staticmethod
    def get(db: Session, ticket_id: uuid.UUID) -> Ticket:
        from app.repositories.tickets import TicketRepository

        ticket = TicketRepository.get(db, ticket_id)
        if ticket is None:
            raise not_found("تیکت یافت نشد.")
        return ticket

    @staticmethod
    def list(
        db: Session,
        *,
        project_id: uuid.UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Ticket], int]:
        from app.repositories.tickets import TicketRepository

        return TicketRepository.list(
            db, project_id=project_id, status=status, page=page, page_size=page_size
        )

    @staticmethod
    def create(
        db: Session,
        *,
        project: Project,
        subject: str,
        body: str,
        created_by_type: str,
        member: ProjectMember | None,
        admin_id: uuid.UUID | None,
        actor: Actor,
        channel: str = "web",
        priority: str = "normal",
    ) -> Ticket:
        if project.archived_at is not None:
            raise conflict("پروژه بایگانی شده است و تیکت جدید نمی پذیرد.")
        now = utcnow()
        clean_subject = TicketService._clean(subject, limit=SUBJECT_LIMIT, field="موضوع")
        clean_body = TicketService._clean(body, limit=BODY_LIMIT, field="متن پیام")
        from_admin = created_by_type == TicketAuthorType.ADMIN.value
        ticket = Ticket(
            project_id=project.id,
            member_id=member.id if member else None,
            subject=clean_subject,
            status=(
                TicketStatus.PENDING_EMPLOYER.value
                if from_admin
                else TicketStatus.PENDING_ADMIN.value
            ),
            priority=priority,
            created_by_type=created_by_type,
            created_by_admin_id=admin_id,
            admin_unread=0 if from_admin else 1,
            member_unread=1 if from_admin else 0,
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(ticket)
        db.flush()
        message = TicketMessage(
            ticket_id=ticket.id,
            author_type=created_by_type,
            author_admin_id=admin_id,
            author_member_id=member.id if member else None,
            author_label=TicketService._author_label(created_by_type, member),
            body=clean_body,
            channel=channel,
            created_at=now,
        )
        db.add(message)
        db.flush()
        AuditService.record(
            db,
            actor=actor,
            action="ticket.created",
            entity_type="ticket",
            entity_id=ticket.id,
            project_id=project.id,
            context={"channel": channel, "subject": clean_subject[:120]},
            now=now,
        )
        TicketService._notify_admin(db, ticket=ticket, message=message, now=now)
        return ticket

    @staticmethod
    def _author_label(author_type: str, member: ProjectMember | None) -> str | None:
        if author_type == TicketAuthorType.ADMIN.value:
            return "تیم نت نووا"
        if member is not None and member.telegram_user is not None:
            user = member.telegram_user
            name = " ".join(part for part in (user.first_name, user.last_name) if part)
            return name or (f"@{user.username}" if user.username else str(user.telegram_id))
        return "کارفرما"

    @staticmethod
    def reply(
        db: Session,
        *,
        ticket: Ticket,
        body: str,
        author_type: str,
        admin_id: uuid.UUID | None = None,
        member: ProjectMember | None = None,
        actor: Actor,
        channel: str = "web",
    ) -> Ticket:
        now = utcnow()
        clean_body = TicketService._clean(body, limit=BODY_LIMIT, field="متن پیام")
        if ticket.status == TicketStatus.CLOSED.value:
            # Replying reopens the thread; this is explicit and audited.
            ticket.status = (
                TicketStatus.PENDING_ADMIN.value
                if author_type == TicketAuthorType.EMPLOYER.value
                else TicketStatus.PENDING_EMPLOYER.value
            )
            ticket.closed_at = None
        elif author_type == TicketAuthorType.ADMIN.value:
            ticket.status = TicketStatus.PENDING_EMPLOYER.value
        else:
            ticket.status = TicketStatus.PENDING_ADMIN.value

        message = TicketMessage(
            ticket_id=ticket.id,
            author_type=author_type,
            author_admin_id=admin_id,
            author_member_id=member.id if member else None,
            author_label=TicketService._author_label(author_type, member),
            body=clean_body,
            channel=channel,
            created_at=now,
        )
        db.add(message)
        ticket.last_message_at = now
        ticket.updated_at = now
        if author_type == TicketAuthorType.ADMIN.value:
            ticket.member_unread += 1
            ticket.admin_unread = 0
        else:
            ticket.admin_unread += 1
            ticket.member_unread = 0
        db.flush()
        AuditService.record(
            db,
            actor=actor,
            action="ticket.replied",
            entity_type="ticket",
            entity_id=ticket.id,
            project_id=ticket.project_id,
            context={"author_type": author_type},
            now=now,
        )
        if author_type == TicketAuthorType.ADMIN.value:
            TicketService._enqueue_employer_notice(db, ticket=ticket, message=message, now=now)
        else:
            TicketService._notify_admin(db, ticket=ticket, message=message, now=now)
        return ticket

    @staticmethod
    def set_status(
        db: Session,
        *,
        ticket: Ticket,
        status: str,
        actor: Actor,
    ) -> Ticket:
        allowed = {
            TicketStatus.OPEN.value,
            TicketStatus.PENDING_ADMIN.value,
            TicketStatus.PENDING_EMPLOYER.value,
            TicketStatus.CLOSED.value,
        }
        if status not in allowed:
            raise conflict("وضعیت تیکت معتبر نیست.")
        now = utcnow()
        ticket.status = status
        ticket.closed_at = now if status == TicketStatus.CLOSED.value else None
        ticket.updated_at = now
        if status == TicketStatus.CLOSED.value:
            ticket.admin_unread = 0
        AuditService.record(
            db,
            actor=actor,
            action="ticket.status_changed",
            entity_type="ticket",
            entity_id=ticket.id,
            project_id=ticket.project_id,
            context={"status": status},
            now=now,
        )
        db.flush()
        return ticket

    @staticmethod
    def mark_read_by_admin(db: Session, ticket: Ticket) -> None:
        if ticket.admin_unread:
            ticket.admin_unread = 0
            db.flush()

    @staticmethod
    def open_count(db: Session, project_id: uuid.UUID | None = None) -> int:
        query = select(func.count(Ticket.id)).where(Ticket.status != TicketStatus.CLOSED.value)
        if project_id is not None:
            query = query.where(Ticket.project_id == project_id)
        return int(db.scalar(query) or 0)

    @staticmethod
    def employer_tickets(
        db: Session, *, project_id: uuid.UUID, member_id: uuid.UUID, limit: int = 6
    ) -> list[Ticket]:
        from app.repositories.tickets import TicketRepository

        return TicketRepository.for_member(
            db, project_id=project_id, member_id=member_id, limit=limit
        )

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    @staticmethod
    def _notify_admin(
        db: Session, *, ticket: Ticket, message: TicketMessage, now: datetime
    ) -> None:
        """Queue a short alert for the agency (never the full conversation)."""
        settings = get_settings()
        if not settings.admin_telegram_chat_id:
            return
        JobRepository.enqueue(
            db,
            kind=JobKind.TICKET_NOTIFY.value,
            payload={
                "target": "admin",
                "ticket_id": str(ticket.id),
                "message_id": str(message.id),
            },
            run_at=now + timedelta(seconds=1),
            now=now,
            max_attempts=settings.job_max_attempts,
            dedupe_key=f"ticket-admin:{message.id}",
        )

    @staticmethod
    def _enqueue_employer_notice(
        db: Session, *, ticket: Ticket, message: TicketMessage, now: datetime
    ) -> None:
        settings = get_settings()
        if ticket.member_id is None:
            return
        JobRepository.enqueue(
            db,
            kind=JobKind.TICKET_NOTIFY.value,
            payload={
                "target": "employer",
                "ticket_id": str(ticket.id),
                "message_id": str(message.id),
                "member_id": str(ticket.member_id),
            },
            run_at=now + timedelta(seconds=1),
            now=now,
            max_attempts=settings.job_max_attempts,
            dedupe_key=f"ticket-employer:{message.id}",
        )


def clean_for_telegram(value: str, limit: int = 350) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def actor_for_employer(member: ProjectMember) -> Actor:
    """Audit actor for actions initiated by an employer inside the bot."""
    label = "کارفرما"
    if member.telegram_user is not None:
        user = member.telegram_user
        label = " ".join(part for part in (user.first_name, user.last_name) if part) or (
            f"@{user.username}" if user.username else str(user.telegram_id)
        )
    return Actor(type="telegram_user", id=member.id, label=label[:120])
