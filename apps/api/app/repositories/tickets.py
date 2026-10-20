from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.project import Project
from app.models.telegram import ProjectMember
from app.models.ticket import Ticket


class TicketRepository:
    _loads = (
        selectinload(Ticket.messages),
        selectinload(Ticket.project)
        .selectinload(Project.members)
        .selectinload(ProjectMember.telegram_user),
    )

    @staticmethod
    def get(db: Session, ticket_id: uuid.UUID) -> Ticket | None:
        return db.scalar(
            select(Ticket).where(Ticket.id == ticket_id).options(*TicketRepository._loads)
        )

    @staticmethod
    def list(
        db: Session,
        *,
        project_id: uuid.UUID | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Ticket], int]:
        query = select(Ticket)
        count_query = select(func.count(Ticket.id))
        filters = []
        if project_id is not None:
            filters.append(Ticket.project_id == project_id)
        if status is not None:
            filters.append(Ticket.status == status)
        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)
        total = int(db.scalar(count_query) or 0)
        items = list(
            db.scalars(
                query.options(*TicketRepository._loads)
                .order_by(Ticket.last_message_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    @staticmethod
    def unread_counts(db: Session, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not project_ids:
            return {}
        rows = db.execute(
            select(Ticket.project_id, func.count(Ticket.id))
            .where(Ticket.project_id.in_(project_ids), Ticket.status != "closed")
            .group_by(Ticket.project_id)
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    @staticmethod
    def for_member(
        db: Session, *, project_id: uuid.UUID, member_id: uuid.UUID, limit: int
    ) -> list[Ticket]:
        return list(
            db.scalars(
                select(Ticket)
                .where(Ticket.project_id == project_id, Ticket.member_id == member_id)
                .options(selectinload(Ticket.messages))
                .order_by(Ticket.last_message_at.desc())
                .limit(limit)
            ).all()
        )
