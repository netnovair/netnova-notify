from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.payment import Payment


class PaymentRepository:
    @staticmethod
    def get(db: Session, payment_id: uuid.UUID, *, lock: bool = False) -> Payment | None:
        query = select(Payment).where(Payment.id == payment_id)
        if lock:
            query = query.with_for_update()
        return db.scalar(query)

    @staticmethod
    def list_for_project(
        db: Session,
        project_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
    ) -> tuple[list[Payment], int]:
        filters = [Payment.project_id == project_id]
        if status:
            filters.append(Payment.status == status)
        total = int(db.scalar(select(func.count(Payment.id)).where(*filters)) or 0)
        items = list(
            db.scalars(
                select(Payment)
                .where(*filters)
                .order_by(Payment.due_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    @staticmethod
    def list_all(
        db: Session,
        *,
        project_id: uuid.UUID | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[Payment, str]], int]:
        from app.models.project import Project

        filters = []
        if project_id:
            filters.append(Payment.project_id == project_id)
        if status:
            filters.append(Payment.status == status)
        total = int(
            db.scalar(
                select(func.count(Payment.id))
                .join(Project, Payment.project_id == Project.id)
                .where(*filters)
            )
            or 0
        )
        rows = db.execute(
            select(Payment, Project.name)
            .join(Project, Payment.project_id == Project.id)
            .where(*filters)
            .order_by(Payment.due_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [(row[0], row[1]) for row in rows], total

    @staticmethod
    def open_payments_for_project(db: Session, project_id: uuid.UUID) -> list[Payment]:
        return list(
            db.scalars(
                select(Payment)
                .where(Payment.project_id == project_id, Payment.status == "unpaid")
                .order_by(Payment.due_at)
            ).all()
        )

    @staticmethod
    def open_count(db: Session) -> int:
        return int(db.scalar(select(func.count(Payment.id)).where(Payment.status == "unpaid")) or 0)

    @staticmethod
    def open_totals_by_currency(db: Session) -> dict[str, int]:
        rows = db.execute(
            select(Payment.currency, func.coalesce(func.sum(Payment.amount_minor), 0))
            .where(Payment.status == "unpaid")
            .group_by(Payment.currency)
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    @staticmethod
    def unpaid_due_on(db: Session, day_start: datetime, day_end: datetime) -> list[Payment]:
        return list(
            db.scalars(
                select(Payment).where(
                    Payment.status == "unpaid",
                    Payment.due_at >= day_start,
                    Payment.due_at < day_end,
                )
            ).all()
        )
