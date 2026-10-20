from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import conflict, not_found
from app.core.security import utcnow
from app.domain.enums import (
    JobKind,
    NotificationStatus,
    NotificationType,
    PaymentStatus,
)
from app.domain.jalali import format_jalali_date
from app.domain.payments import format_amount, reminder_at
from app.models.job import ScheduledJob
from app.models.payment import Payment
from app.models.project import Project
from app.repositories.jobs import JobRepository
from app.repositories.payments import PaymentRepository
from app.repositories.projects import ProjectRepository
from app.schemas.payment import PaymentCreate, PaymentUpdate
from app.services.audit import SYSTEM_ACTOR, Actor, AuditService

logger = logging.getLogger(__name__)


class PaymentService:
    @staticmethod
    def get(db: Session, payment_id) -> Payment:
        payment = PaymentRepository.get(db, payment_id)
        if payment is None:
            raise not_found("پرداخت یافت نشد.")
        return payment

    @staticmethod
    def create(
        db: Session,
        *,
        project: Project,
        payload: PaymentCreate,
        actor: Actor,
    ) -> Payment:
        now = utcnow()
        payment = Payment(
            project_id=project.id,
            title=payload.title,
            amount_minor=payload.amount_minor,
            currency=payload.currency.value,
            due_at=payload.due_at,
            status=PaymentStatus.UNPAID.value,
            notes=payload.notes,
            created_by=actor.id if actor.type == "admin" else None,
            created_at=now,
            updated_at=now,
        )
        db.add(payment)
        db.flush()

        PaymentService._schedule_reminder(db, payment, project, now)
        AuditService.record(
            db,
            actor=actor,
            action="payment.created",
            entity_type="payment",
            entity_id=payment.id,
            project_id=project.id,
            context={
                "amount_minor": payment.amount_minor,
                "currency": payment.currency,
                "due_at": payment.due_at.isoformat(),
                "reminder_job_id": str(payment.reminder_job_id)
                if payment.reminder_job_id
                else None,
            },
            now=now,
        )
        return payment

    @staticmethod
    def update(db: Session, *, payment: Payment, payload: PaymentUpdate, actor: Actor) -> Payment:
        now = utcnow()
        if payment.status == PaymentStatus.PAID.value:
            raise conflict("پرداخت تسویه شده قابل ویرایش نیست.")
        if payment.status == PaymentStatus.CANCELLED.value:
            raise conflict("پرداخت لغو شده قابل ویرایش نیست.")
        data = payload.model_dump(exclude_unset=True)

        if data.get("status") == "cancelled":
            return PaymentService.cancel(db, payment=payment, actor=actor)

        changed: dict[str, object] = {}
        old_due = payment.due_at
        for field in ("title", "amount_minor", "currency", "due_at", "notes"):
            if field not in data or data[field] is None:
                continue
            value = data[field]
            if field == "currency":
                value = value.value if hasattr(value, "value") else value
            if getattr(payment, field) != value:
                setattr(payment, field, value)
                changed[field] = value

        payment.updated_at = now
        if changed:
            project = db.get(Project, payment.project_id)
            assert project is not None
            if "due_at" in changed and payment.due_at != old_due:
                PaymentService._schedule_reminder(db, payment, project, now)
            AuditService.record(
                db,
                actor=actor,
                action="payment.updated",
                entity_type="payment",
                entity_id=payment.id,
                project_id=payment.project_id,
                context={"changed": sorted(changed.keys())},
                now=now,
            )
            db.flush()
        return payment

    @staticmethod
    def mark_paid(db: Session, *, payment: Payment, actor: Actor) -> Payment:
        now = utcnow()
        if payment.status == PaymentStatus.PAID.value:
            return payment
        if payment.status not in (
            PaymentStatus.UNPAID.value,
            PaymentStatus.PARTIALLY_PAID.value,
        ):
            raise conflict("این پرداخت در وضعیت فعلی قابل تسویه نیست.")
        payment.status = PaymentStatus.PAID.value
        payment.amount_paid_minor = payment.amount_minor
        payment.paid_at = now
        payment.updated_at = now
        JobRepository.cancel(db, payment.reminder_job_id, now)
        payment.reminder_job_id = None
        AuditService.record(
            db,
            actor=actor,
            action="payment.marked_paid",
            entity_type="payment",
            entity_id=payment.id,
            project_id=payment.project_id,
            context={"amount_minor": payment.amount_minor, "currency": payment.currency},
            now=now,
        )
        db.flush()
        return payment

    @staticmethod
    def cancel(db: Session, *, payment: Payment, actor: Actor) -> Payment:
        now = utcnow()
        if payment.status == PaymentStatus.PAID.value:
            raise conflict("پرداخت تسویه شده قابل لغو نیست.")
        if payment.status == PaymentStatus.CANCELLED.value:
            return payment
        payment.status = PaymentStatus.CANCELLED.value
        payment.amount_paid_minor = 0
        payment.cancelled_at = now
        payment.updated_at = now
        JobRepository.cancel(db, payment.reminder_job_id, now)
        payment.reminder_job_id = None
        AuditService.record(
            db,
            actor=actor,
            action="payment.cancelled",
            entity_type="payment",
            entity_id=payment.id,
            project_id=payment.project_id,
            context={"amount_minor": payment.amount_minor, "currency": payment.currency},
            now=now,
        )
        db.flush()
        return payment

    @staticmethod
    def _schedule_reminder(
        db: Session, payment: Payment, project: Project, now: datetime
    ) -> ScheduledJob | None:
        settings = get_settings()
        JobRepository.cancel(db, payment.reminder_job_id, now)
        payment.reminder_job_id = None

        if payment.status != PaymentStatus.UNPAID.value or project.status != "active":
            return None
        run_at = reminder_at(payment.due_at, now, settings.payment_reminder_days_before)
        if run_at is None:
            return None
        job = JobRepository.enqueue(
            db,
            kind=JobKind.PAYMENT_REMINDER.value,
            payload={
                "payment_id": str(payment.id),
                "project_id": str(payment.project_id),
                "due_at": payment.due_at.isoformat(),
            },
            run_at=run_at,
            now=now,
            max_attempts=min(settings.job_max_attempts, 3),
            dedupe_key=f"payment-reminder:{payment.id}:{payment.due_at.isoformat()}",
        )
        if job is not None:
            payment.reminder_job_id = job.id
            db.flush()
            AuditService.record(
                db,
                actor=SYSTEM_ACTOR,
                action="payment.reminder_scheduled",
                entity_type="payment",
                entity_id=payment.id,
                project_id=payment.project_id,
                context={"run_at": run_at.isoformat(), "job_id": str(job.id)},
                now=now,
            )
        return job

    # ------------------------------------------------------------------
    # Worker handler
    # ------------------------------------------------------------------
    @staticmethod
    def handle_reminder(db: Session, job: ScheduledJob, adapter) -> None:
        """Send at most one reminder notification per scheduled job.

        The notification id is persisted on the job so a retry after a
        transient failure resumes the same notification instead of creating a
        duplicate one.
        """
        from app.services.notifications import NotificationService

        now = utcnow()
        payment_id = job.payload.get("payment_id")
        if not payment_id:
            PaymentService._skip(db, job, None, "شناسه پرداخت در کار موجود نیست.", now)
            return

        payment = PaymentRepository.get(db, payment_id, lock=True)
        if payment is None:
            PaymentService._skip(db, job, None, "پرداخت یافت نشد.", now)
            return

        if payment.status not in (
            PaymentStatus.UNPAID.value,
            PaymentStatus.PARTIALLY_PAID.value,
        ):
            PaymentService._skip(db, job, payment, "پرداخت دیگری در وضعیت باز نیست.", now)
            return

        if job.payload.get("due_at") and job.payload["due_at"] != payment.due_at.isoformat():
            PaymentService._skip(
                db, job, payment, "موعد پرداخت تغییر کرده و این یادآوری منقضی شده است.", now
            )
            return

        project = db.get(Project, payment.project_id)
        if project is None or project.status != "active":
            PaymentService._skip(db, job, payment, "پروژه غیرفعال است.", now)
            return

        members = [
            member
            for member in ProjectRepository.active_members(db, project.id)
            if member.telegram_user is not None
        ]
        if not members:
            PaymentService._skip(
                db, job, payment, "کارفرمای تاییدشده ای برای ارسال یادآوری وجود ندارد.", now
            )
            return

        notification_id = job.payload.get("notification_id")
        notification = None
        if notification_id:
            from app.models.notification import Notification

            notification = db.get(Notification, notification_id)
        if notification is None:
            from app.models.notification import Notification

            body = PaymentService._reminder_body(db, payment, project)
            notification = Notification(
                project_id=project.id,
                type=NotificationType.FINANCIAL.value,
                title=f"یادآوری پرداخت: {payment.title}",
                body=body,
                status=NotificationStatus.QUEUED.value,
                queued_at=now,
                attempt_count=0,
                created_at=now,
                updated_at=now,
            )
            db.add(notification)
            db.flush()
            job.payload = {**job.payload, "notification_id": str(notification.id)}
            job.updated_at = now
            db.flush()

        status = NotificationService.deliver(
            db, notification=notification, adapter=adapter, now=now
        )
        if status == NotificationStatus.SENT.value:
            AuditService.record(
                db,
                actor=SYSTEM_ACTOR,
                action="payment.reminder_sent",
                entity_type="payment",
                entity_id=payment.id,
                project_id=project.id,
                context={"notification_id": str(notification.id)},
                now=utcnow(),
            )
            db.flush()

    @staticmethod
    def _reminder_body(db: Session, payment: Payment, project: Project) -> str:
        """Render the editable ``payment_reminder`` template (project > global > default)."""
        from app.domain.accounting import invoice_remaining
        from app.services.accounting import TemplateService

        settings = get_settings()
        remaining = invoice_remaining(payment.amount_minor, payment.amount_paid_minor)
        text = TemplateService.render(
            db,
            "payment_reminder",
            project_id=payment.project_id,
            values={
                "project": project.name,
                "name": project.client_name or "",
                "amount": format_amount(payment.amount_minor, payment.currency),
                "due": format_jalali_date(payment.due_at, settings.tehran_timezone),
                "remaining": format_amount(remaining, payment.currency),
            },
        )
        notes = f"\nتوضیحات: {payment.notes}" if payment.notes else ""
        return (
            f"{text}{notes}\n\n"
            "این پیام فقط برای اطلاع رسانی وضعیت مالی است و به معنای تایید تراکنش بانکی نیست."
        )

    @staticmethod
    def _skip(
        db: Session, job: ScheduledJob, payment: Payment | None, reason: str, now: datetime
    ) -> None:
        logger.info("Payment reminder skipped: %s", reason)
        job.last_error = reason[:1000]
        if payment is not None:
            AuditService.record(
                db,
                actor=SYSTEM_ACTOR,
                action="payment.reminder_skipped",
                entity_type="payment",
                entity_id=payment.id,
                project_id=payment.project_id,
                context={"reason": reason},
                now=now,
            )
        db.flush()
