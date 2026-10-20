"""Light accounting: invoices, receipts, allocation and the texts around them.

The service is deliberately boring: every mutation recomputes the invoice totals
from ``payment_allocations`` inside the same transaction, so the denormalised
``payments.amount_paid_minor`` can never drift from the receipt history.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.errors import bad_request, conflict, not_found
from app.core.security import utcnow
from app.domain.accounting import (
    Totals,
    auto_allocate,
    invoice_remaining,
    invoice_status,
    totals_for,
)
from app.domain.attachments import (
    MAX_ATTACHMENTS_PER_MESSAGE,
    AttachmentError,
    AttachmentInput,
    sha256_hex,
    validate_attachment,
)
from app.domain.enums import JobKind, NotificationType, PaymentStatus, ReceiptStatus
from app.domain.message_templates import DEFAULTS, TemplateDefinition, render_template
from app.domain.payments import format_amount
from app.models.accounting import (
    MessageTemplate,
    PaymentAllocation,
    PaymentMethod,
    PaymentReceipt,
    PaymentReceiptFile,
)
from app.models.payment import Payment
from app.models.project import Project
from app.repositories.jobs import JobRepository
from app.schemas.accounting import (
    AccountingOverviewOut,
    AllocationIn,
    AllocationOut,
    CurrencyTotalsOut,
    MessageTemplateOut,
    ProjectAccountingOut,
    ReceiptFileOut,
    ReceiptOut,
)
from app.services.audit import Actor, AuditService

logger = logging.getLogger(__name__)

MAX_RECEIPT_AMOUNT = 10**15


# ---------------------------------------------------------------------------
# Payment methods (card numbers shown in the bot)
# ---------------------------------------------------------------------------
class PaymentMethodService:
    @staticmethod
    def list(db: Session, *, project_id: uuid.UUID | None = None) -> list[PaymentMethod]:
        """Global rows, or the global rows plus the ones scoped to ``project_id``."""
        stmt = select(PaymentMethod).order_by(PaymentMethod.order_index, PaymentMethod.created_at)
        if project_id is None:
            stmt = stmt.where(PaymentMethod.project_id.is_(None))
        else:
            stmt = stmt.where(
                or_(
                    PaymentMethod.project_id == project_id,
                    PaymentMethod.project_id.is_(None),
                )
            )
        return list(db.scalars(stmt).all())

    @staticmethod
    def for_project(db: Session, project_id: uuid.UUID) -> list[PaymentMethod]:
        """Project-specific rows win; otherwise the global defaults are used."""
        rows = PaymentMethodService.list(db, project_id=project_id)
        scoped = [row for row in rows if row.is_active and row.project_id == project_id]
        if scoped:
            return scoped
        return [row for row in rows if row.is_active and row.project_id is None]

    @staticmethod
    def get(db: Session, method_id: uuid.UUID) -> PaymentMethod:
        row = db.get(PaymentMethod, method_id)
        if row is None:
            raise not_found("شماره کارت یافت نشد.")
        return row

    @staticmethod
    def create(db: Session, *, payload, actor: Actor) -> PaymentMethod:
        now = utcnow()
        row = PaymentMethod(
            project_id=payload.project_id,
            title=payload.title,
            card_number=payload.card_number,
            holder_name=payload.holder_name,
            bank_name=payload.bank_name,
            note=payload.note,
            is_active=payload.is_active,
            order_index=payload.order_index,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.flush()
        AuditService.record(
            db,
            actor=actor,
            action="payment_method.created",
            entity_type="payment_method",
            entity_id=row.id,
            project_id=row.project_id,
            context={"title": row.title, "card_last4": row.card_number[-4:]},
            now=now,
        )
        return row

    @staticmethod
    def update(db: Session, *, row: PaymentMethod, payload, actor: Actor) -> PaymentMethod:
        now = utcnow()
        for field in (
            "title",
            "card_number",
            "holder_name",
            "bank_name",
            "note",
            "is_active",
            "order_index",
            "project_id",
        ):
            value = getattr(payload, field, None)
            if value is not None:
                setattr(row, field, value)
        row.updated_at = now
        AuditService.record(
            db,
            actor=actor,
            action="payment_method.updated",
            entity_type="payment_method",
            entity_id=row.id,
            project_id=row.project_id,
            context={"title": row.title, "card_last4": row.card_number[-4:]},
            now=now,
        )
        db.flush()
        return row

    @staticmethod
    def delete(db: Session, *, row: PaymentMethod, actor: Actor) -> None:
        AuditService.record(
            db,
            actor=actor,
            action="payment_method.deleted",
            entity_type="payment_method",
            entity_id=row.id,
            project_id=row.project_id,
            context={"title": row.title, "card_last4": row.card_number[-4:]},
            now=utcnow(),
        )
        db.delete(row)
        db.flush()


# ---------------------------------------------------------------------------
# Editable message templates
# ---------------------------------------------------------------------------
def template_output(
    definition: TemplateDefinition,
    *,
    row: MessageTemplate | None,
    project_id: uuid.UUID | None,
) -> MessageTemplateOut:
    return MessageTemplateOut(
        key=definition.key,
        title=definition.title,
        description=definition.description,
        body=row.body if row else definition.body,
        default_body=definition.body,
        variables=list(definition.variables),
        customized=row is not None,
        project_id=project_id,
        updated_at=row.updated_at if row else None,
    )


class TemplateService:
    @staticmethod
    def resolve_row(
        db: Session, key: str, *, project_id: uuid.UUID | None = None
    ) -> MessageTemplate | None:
        if key not in DEFAULTS:
            raise not_found("متن آماده یافت نشد.")
        if project_id is not None:
            row = db.scalar(
                select(MessageTemplate).where(
                    MessageTemplate.key == key, MessageTemplate.project_id == project_id
                )
            )
            if row is not None:
                return row
        return db.scalar(
            select(MessageTemplate).where(
                MessageTemplate.key == key, MessageTemplate.project_id.is_(None)
            )
        )

    @staticmethod
    def render(
        db: Session, key: str, *, project_id: uuid.UUID | None, values: dict[str, str]
    ) -> str:
        definition = DEFAULTS.get(key)
        if definition is None:
            raise not_found("متن آماده یافت نشد.")
        row = TemplateService.resolve_row(db, key, project_id=project_id)
        body = row.body if row is not None else definition.body
        return render_template(body, values)

    @staticmethod
    def list(db: Session, *, project_id: uuid.UUID | None = None) -> list[MessageTemplateOut]:
        scope = (
            MessageTemplate.project_id == project_id
            if project_id
            else MessageTemplate.project_id.is_(None)
        )
        rows = {row.key: row for row in db.scalars(select(MessageTemplate).where(scope)).all()}
        return [
            template_output(definition, row=rows.get(key), project_id=project_id)
            for key, definition in DEFAULTS.items()
        ]

    @staticmethod
    def upsert(db: Session, *, key: str, body: str, project_id: uuid.UUID | None, actor: Actor):
        definition = DEFAULTS.get(key)
        if definition is None:
            raise not_found("متن آماده یافت نشد.")
        text = (body or "").strip()
        if len(text) < 2:
            raise bad_request("متن آماده نمی تواند خالی باشد.")
        now = utcnow()
        row = db.scalar(
            select(MessageTemplate).where(
                MessageTemplate.key == key,
                MessageTemplate.project_id == project_id
                if project_id
                else MessageTemplate.project_id.is_(None),
            )
        )
        if row is None:
            row = MessageTemplate(
                project_id=project_id,
                key=key,
                title=definition.title,
                body=text,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        else:
            row.body = text
            row.updated_at = now
        db.flush()
        AuditService.record(
            db,
            actor=actor,
            action="message_template.updated",
            entity_type="message_template",
            entity_id=row.id,
            project_id=project_id,
            context={"key": key},
            now=now,
        )
        return template_output(definition, row=row, project_id=project_id)

    @staticmethod
    def reset(db: Session, *, key: str, project_id: uuid.UUID | None, actor: Actor):
        definition = DEFAULTS.get(key)
        if definition is None:
            raise not_found("متن آماده یافت نشد.")
        row = db.scalar(
            select(MessageTemplate).where(
                MessageTemplate.key == key,
                MessageTemplate.project_id == project_id
                if project_id
                else MessageTemplate.project_id.is_(None),
            )
        )
        if row is not None:
            db.delete(row)
            db.flush()
            AuditService.record(
                db,
                actor=actor,
                action="message_template.reset",
                entity_type="message_template",
                entity_id=row.id,
                project_id=project_id,
                context={"key": key},
                now=utcnow(),
            )
        return template_output(definition, row=None, project_id=project_id)


# ---------------------------------------------------------------------------
# Receipts and allocation
# ---------------------------------------------------------------------------
class AccountingService:
    # -- reads ---------------------------------------------------------
    @staticmethod
    def invoices(db: Session, project_id: uuid.UUID) -> list[Payment]:
        return list(
            db.scalars(
                select(Payment)
                .where(Payment.project_id == project_id)
                .order_by(Payment.due_at, Payment.created_at)
            ).all()
        )

    @staticmethod
    def credit(db: Session, project_id: uuid.UUID, currency: str) -> int:
        """Approved receipts minus everything allocated from them."""
        received = (
            db.scalar(
                select(func.coalesce(func.sum(PaymentReceipt.amount_minor), 0)).where(
                    PaymentReceipt.project_id == project_id,
                    PaymentReceipt.currency == currency,
                    PaymentReceipt.status == ReceiptStatus.APPROVED.value,
                )
            )
            or 0
        )
        allocated = (
            db.scalar(
                select(func.coalesce(func.sum(PaymentAllocation.amount_minor), 0))
                .join(PaymentReceipt, PaymentReceipt.id == PaymentAllocation.receipt_id)
                .where(
                    PaymentReceipt.project_id == project_id,
                    PaymentReceipt.currency == currency,
                    PaymentReceipt.status == ReceiptStatus.APPROVED.value,
                )
            )
            or 0
        )
        return max(0, int(received) - int(allocated))

    @staticmethod
    def pending_receipts(db: Session, project_id: uuid.UUID) -> int:
        return int(
            db.scalar(
                select(func.count(PaymentReceipt.id)).where(
                    PaymentReceipt.project_id == project_id,
                    PaymentReceipt.status == ReceiptStatus.PENDING.value,
                )
            )
            or 0
        )

    @staticmethod
    def project_totals(
        db: Session, project_id: uuid.UUID, *, now: datetime | None = None
    ) -> list[Totals]:
        now = now or utcnow()
        invoices = AccountingService.invoices(db, project_id)
        currencies = sorted({invoice.currency for invoice in invoices}) or ["IRT"]
        results = []
        for currency in currencies:
            results.append(
                totals_for(
                    invoices,
                    currency=currency,
                    credit_minor=AccountingService.credit(db, project_id, currency),
                    now=now,
                )
            )
        return results

    @staticmethod
    def overview(db: Session, *, now: datetime | None = None) -> AccountingOverviewOut:
        now = now or utcnow()
        projects = list(
            db.scalars(
                select(Project).where(Project.archived_at.is_(None)).order_by(Project.name)
            ).all()
        )
        combined: dict[str, dict[str, int]] = {}
        rows: list[ProjectAccountingOut] = []
        for project in projects:
            totals = AccountingService.project_totals(db, project.id, now=now)
            payloads = []
            for total in totals:
                pending = AccountingService.pending_receipts(db, project.id)
                payload = CurrencyTotalsOut(
                    currency=total.currency,
                    debt_minor=total.debt_minor,
                    paid_minor=total.paid_minor,
                    overdue_minor=total.overdue_minor,
                    credit_minor=total.credit_minor,
                    balance_minor=total.balance_minor,
                    invoices_total=total.invoices_total,
                    invoices_open=total.invoices_open,
                    pending_receipts=pending,
                    settled=total.settled,
                )
                payloads.append(payload)
                bucket = combined.setdefault(
                    total.currency,
                    {"debt": 0, "paid": 0, "overdue": 0, "credit": 0, "open": 0, "total": 0},
                )
                bucket["debt"] += total.debt_minor
                bucket["paid"] += total.paid_minor
                bucket["overdue"] += total.overdue_minor
                bucket["credit"] += total.credit_minor
                bucket["open"] += total.invoices_open
                bucket["total"] += total.invoices_total
            if payloads:
                rows.append(
                    ProjectAccountingOut(
                        project_id=project.id, project_name=project.name, totals=payloads
                    )
                )
        summary = [
            CurrencyTotalsOut(
                currency=currency,
                debt_minor=bucket["debt"],
                paid_minor=bucket["paid"],
                overdue_minor=bucket["overdue"],
                credit_minor=bucket["credit"],
                balance_minor=max(0, bucket["debt"] - bucket["credit"]),
                invoices_total=bucket["total"],
                invoices_open=bucket["open"],
                pending_receipts=int(
                    db.scalar(
                        select(func.count(PaymentReceipt.id)).where(
                            PaymentReceipt.currency == currency,
                            PaymentReceipt.status == ReceiptStatus.PENDING.value,
                        )
                    )
                    or 0
                ),
                settled=max(0, bucket["debt"] - bucket["credit"]) == 0,
            )
            for currency, bucket in sorted(combined.items())
        ]
        return AccountingOverviewOut(totals=summary, projects=rows)

    @staticmethod
    def receipt_out(receipt: PaymentReceipt, *, project_name: str | None = None) -> ReceiptOut:
        titles = {allocation.payment_id: allocation.payment for allocation in receipt.allocations}
        return ReceiptOut(
            id=receipt.id,
            project_id=receipt.project_id,
            project_name=project_name,
            member_id=receipt.member_id,
            member_display_name=None,
            submitted_by_type=receipt.submitted_by_type,
            amount_minor=receipt.amount_minor,
            currency=receipt.currency,
            tracking_code=receipt.tracking_code,
            note=receipt.note,
            status=receipt.status,
            review_note=receipt.review_note,
            reviewed_at=receipt.reviewed_at,
            channel=receipt.channel,
            files=[
                ReceiptFileOut(
                    id=file.id,
                    filename=file.filename,
                    content_type=file.content_type,
                    size_bytes=file.size_bytes,
                )
                for file in receipt.files
            ],
            allocations=[
                AllocationOut(
                    id=allocation.id,
                    payment_id=allocation.payment_id,
                    payment_title=(
                        titles[allocation.payment_id].title
                        if titles.get(allocation.payment_id) is not None
                        else None
                    ),
                    amount_minor=allocation.amount_minor,
                )
                for allocation in receipt.allocations
            ],
            created_at=receipt.created_at,
        )

    @staticmethod
    def get_receipt(db: Session, receipt_id: uuid.UUID) -> PaymentReceipt:
        receipt = db.scalar(
            select(PaymentReceipt)
            .where(PaymentReceipt.id == receipt_id)
            .options(
                selectinload(PaymentReceipt.files),
                selectinload(PaymentReceipt.allocations).selectinload(PaymentAllocation.payment),
            )
        )
        if receipt is None:
            raise not_found("رسید پرداخت یافت نشد.")
        return receipt

    @staticmethod
    def list_receipts(
        db: Session,
        *,
        project_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[PaymentReceipt]:
        stmt = (
            select(PaymentReceipt)
            .options(
                selectinload(PaymentReceipt.files),
                selectinload(PaymentReceipt.allocations).selectinload(PaymentAllocation.payment),
            )
            .order_by(PaymentReceipt.created_at.desc())
            .limit(limit)
        )
        if project_id is not None:
            stmt = stmt.where(PaymentReceipt.project_id == project_id)
        if status is not None:
            stmt = stmt.where(PaymentReceipt.status == status)
        return list(db.scalars(stmt).all())

    # -- writes --------------------------------------------------------
    @staticmethod
    def recompute_payment(db: Session, payment: Payment, *, now: datetime | None = None) -> Payment:
        now = now or utcnow()
        paid = int(
            db.scalar(
                select(func.coalesce(func.sum(PaymentAllocation.amount_minor), 0))
                .join(PaymentReceipt, PaymentReceipt.id == PaymentAllocation.receipt_id)
                .where(
                    PaymentAllocation.payment_id == payment.id,
                    PaymentReceipt.status == ReceiptStatus.APPROVED.value,
                )
            )
            or 0
        )
        paid = min(paid, payment.amount_minor)
        payment.amount_paid_minor = paid
        new_status = invoice_status(payment.amount_minor, paid, payment.status)
        if new_status != payment.status:
            if new_status == PaymentStatus.PAID.value:
                payment.paid_at = now
                JobRepository.cancel(db, payment.reminder_job_id, now)
                payment.reminder_job_id = None
            elif payment.status == PaymentStatus.PAID.value:
                payment.paid_at = None
            payment.status = new_status
        payment.updated_at = now
        db.flush()
        return payment

    @staticmethod
    def _validate_allocations(
        db: Session,
        *,
        receipt: PaymentReceipt,
        allocations: list[AllocationIn],
    ) -> list[tuple[Payment, int]]:
        if not allocations:
            raise bad_request("حداقل یک فاکتور برای تخصیص انتخاب کنید.")
        total = sum(item.amount_minor for item in allocations)
        if total > receipt.amount_minor:
            raise bad_request(
                "جمع تخصیص ها از مبلغ رسید بیشتر است.", code="allocation_over_receipt"
            )
        seen: set[uuid.UUID] = set()
        prepared: list[tuple[Payment, int]] = []
        for item in allocations:
            if item.payment_id in seen:
                raise bad_request(
                    "هر فاکتور فقط یک بار قابل انتخاب است.", code="duplicate_allocation"
                )
            seen.add(item.payment_id)
            payment = db.get(Payment, item.payment_id)
            if payment is None or payment.project_id != receipt.project_id:
                raise not_found("فاکتور در این پروژه یافت نشد.")
            if payment.status == PaymentStatus.CANCELLED.value:
                raise conflict("فاکتور لغو شده قابل تخصیص نیست.", code="payment_cancelled")
            if payment.currency != receipt.currency:
                raise conflict("ارز رسید و فاکتور یکسان نیست.", code="currency_mismatch")
            remaining = invoice_remaining(payment.amount_minor, payment.amount_paid_minor)
            if item.amount_minor > remaining:
                raise bad_request(
                    f"مبلغ تخصیص برای «{payment.title}» از مانده فاکتور بیشتر است.",
                    code="allocation_exceeds_invoice",
                )
            prepared.append((payment, item.amount_minor))
        return prepared

    @staticmethod
    def _write_allocations(
        db: Session,
        *,
        receipt: PaymentReceipt,
        prepared: list[tuple[Payment, int]],
        now: datetime,
    ) -> None:
        for existing in list(receipt.allocations):
            db.delete(existing)
        db.flush()
        for payment, amount in prepared:
            db.add(
                PaymentAllocation(
                    receipt=receipt,
                    payment=payment,
                    amount_minor=amount,
                    created_at=now,
                )
            )
        db.flush()
        for payment, _ in prepared:
            AccountingService.recompute_payment(db, payment, now=now)

    @staticmethod
    def create_receipt(
        db: Session,
        *,
        project: Project,
        actor: Actor,
        amount_minor: int,
        currency: str = "IRT",
        member_id: uuid.UUID | None = None,
        tracking_code: str | None = None,
        note: str = "",
        attachments: list[AttachmentInput] | None = None,
        channel: str = "web",
        submitted_by_type: str = "admin",
        now: datetime | None = None,
    ) -> PaymentReceipt:
        now = now or utcnow()
        if project.archived_at is not None:
            raise conflict("پروژه بایگانی شده است.")
        if not 0 < amount_minor <= MAX_RECEIPT_AMOUNT:
            raise bad_request("مبلغ رسید معتبر نیست.")
        prepared = AccountingService._prepare_files(attachments)
        receipt = PaymentReceipt(
            project_id=project.id,
            member_id=member_id,
            submitted_by_type=submitted_by_type,
            amount_minor=amount_minor,
            currency=currency,
            tracking_code=(tracking_code or None),
            note=(note or "").strip()[:2000],
            status=ReceiptStatus.PENDING.value,
            review_note="",
            channel=channel,
            created_at=now,
            updated_at=now,
        )
        db.add(receipt)
        db.flush()
        AccountingService._store_files(db, receipt=receipt, prepared=prepared, now=now)
        AuditService.record(
            db,
            actor=actor,
            action="receipt.created",
            entity_type="payment_receipt",
            entity_id=receipt.id,
            project_id=project.id,
            context={
                "amount_minor": receipt.amount_minor,
                "currency": receipt.currency,
                "files": len(prepared),
                "channel": channel,
            },
            now=now,
        )
        AccountingService._notify_admin(db, receipt=receipt, project=project, now=now)
        return receipt

    @staticmethod
    def _prepare_files(attachments: list[AttachmentInput] | None) -> list[tuple[bytes, str, str]]:
        if not attachments:
            return []
        if len(attachments) > MAX_ATTACHMENTS_PER_MESSAGE:
            raise bad_request(
                f"حداکثر {MAX_ATTACHMENTS_PER_MESSAGE} تصویر برای هر رسید مجاز است.",
                code="too_many_attachments",
            )
        prepared = []
        for item in attachments:
            try:
                content_type, filename = validate_attachment(
                    item.data, filename=item.filename, declared_type=item.content_type
                )
            except AttachmentError as exc:
                raise bad_request(str(exc), code="invalid_attachment") from exc
            prepared.append((item.data, filename, content_type))
        return prepared

    @staticmethod
    def _store_files(
        db: Session,
        *,
        receipt: PaymentReceipt,
        prepared: list[tuple[bytes, str, str]],
        now: datetime,
    ) -> None:
        for data, filename, content_type in prepared:
            db.add(
                PaymentReceiptFile(
                    receipt=receipt,
                    filename=filename[:120],
                    content_type=content_type,
                    size_bytes=len(data),
                    sha256=sha256_hex(data),
                    data=data,
                    created_at=now,
                )
            )
        if prepared:
            db.flush()

    @staticmethod
    def approve(
        db: Session,
        *,
        receipt: PaymentReceipt,
        actor: Actor,
        allocations: list[AllocationIn] | None = None,
        note: str = "",
        now: datetime | None = None,
    ) -> PaymentReceipt:
        now = now or utcnow()
        if receipt.status != ReceiptStatus.PENDING.value:
            raise conflict("این رسید قبلا بررسی شده است.", code="receipt_already_reviewed")
        invoices = AccountingService.invoices(db, receipt.project_id)
        of_currency = [invoice for invoice in invoices if invoice.currency == receipt.currency]
        if not of_currency and not allocations:
            raise conflict(
                "فاکتوری با ارز این رسید ثبت نشده است؛ ابتدا فاکتور بسازید یا تخصیص دستی بدهید.",
                code="no_invoice",
            )
        if allocations:
            prepared = AccountingService._validate_allocations(
                db, receipt=receipt, allocations=allocations
            )
        else:
            auto, leftover = auto_allocate(receipt.amount_minor, of_currency)
            prepared = [
                (db.get(Payment, item.payment_id), item.amount_minor)  # type: ignore[arg-type]
                for item in auto
            ]
            if not prepared:
                raise conflict(
                    "هیچ فاکتور بازی برای تخصیص این رسید وجود ندارد.",
                    code="nothing_to_allocate",
                )
            if leftover and not note:
                note = "بخشی از رسید به عنوان اعتبار ذخیره شد."
        receipt.status = ReceiptStatus.APPROVED.value
        receipt.review_note = (note or "").strip()[:2000]
        receipt.reviewed_by = actor.id if actor.type == "admin" else None
        receipt.reviewed_at = now
        receipt.updated_at = now
        AccountingService._write_allocations(db, receipt=receipt, prepared=prepared, now=now)
        AuditService.record(
            db,
            actor=actor,
            action="receipt.approved",
            entity_type="payment_receipt",
            entity_id=receipt.id,
            project_id=receipt.project_id,
            context={
                "amount_minor": receipt.amount_minor,
                "currency": receipt.currency,
                "allocated": [str(payment.id) for payment, _ in prepared],
            },
            now=now,
        )
        AccountingService._queue_result(db, receipt=receipt, approved=True, now=now)
        return receipt

    @staticmethod
    def reject(
        db: Session,
        *,
        receipt: PaymentReceipt,
        actor: Actor,
        reason: str,
        now: datetime | None = None,
    ) -> PaymentReceipt:
        now = now or utcnow()
        if receipt.status != ReceiptStatus.PENDING.value:
            raise conflict("این رسید قبلا بررسی شده است.", code="receipt_already_reviewed")
        text = (reason or "").strip()
        if len(text) < 3:
            raise bad_request("دلیل رد رسید را بنویسید.")
        receipt.status = ReceiptStatus.REJECTED.value
        receipt.review_note = text[:2000]
        receipt.reviewed_by = actor.id if actor.type == "admin" else None
        receipt.reviewed_at = now
        receipt.updated_at = now
        AuditService.record(
            db,
            actor=actor,
            action="receipt.rejected",
            entity_type="payment_receipt",
            entity_id=receipt.id,
            project_id=receipt.project_id,
            context={"reason": text[:300]},
            now=now,
        )
        AccountingService._queue_result(db, receipt=receipt, approved=False, now=now)
        return receipt

    @staticmethod
    def replace_allocations(
        db: Session,
        *,
        receipt: PaymentReceipt,
        allocations: list[AllocationIn],
        actor: Actor,
        now: datetime | None = None,
    ) -> PaymentReceipt:
        """Edit the split after approval (the total can never exceed the receipt)."""
        now = now or utcnow()
        if receipt.status != ReceiptStatus.APPROVED.value:
            raise conflict("تخصیص فقط برای رسید تاییدشده قابل ویرایش است.")
        affected = [allocation.payment for allocation in receipt.allocations]
        # Remove through the collection so the delete-orphan cascade is the only
        # thing that issues the DELETE (an explicit ``db.delete`` here would
        # emit a second, unmatched statement).
        for allocation in list(receipt.allocations):
            receipt.allocations.remove(allocation)
        db.flush()
        for payment in affected:
            AccountingService.recompute_payment(db, payment, now=now)
        prepared = AccountingService._validate_allocations(
            db, receipt=receipt, allocations=allocations
        )
        AccountingService._write_allocations(db, receipt=receipt, prepared=prepared, now=now)
        receipt.updated_at = now
        AuditService.record(
            db,
            actor=actor,
            action="receipt.allocations_updated",
            entity_type="payment_receipt",
            entity_id=receipt.id,
            project_id=receipt.project_id,
            context={"count": len(prepared)},
            now=now,
        )
        return receipt

    # -- notifications -------------------------------------------------
    @staticmethod
    def _notify_admin(
        db: Session, *, receipt: PaymentReceipt, project: Project, now: datetime
    ) -> None:
        settings = get_settings()
        if not settings.admin_telegram_chat_id:
            return
        JobRepository.enqueue(
            db,
            kind=JobKind.RECEIPT_SUBMITTED.value,
            payload={
                "receipt_id": str(receipt.id),
                "project_id": str(project.id),
            },
            run_at=now + timedelta(seconds=1),
            now=now,
            max_attempts=settings.job_max_attempts,
            dedupe_key=f"receipt-admin:{receipt.id}",
        )

    @staticmethod
    def _queue_result(
        db: Session, *, receipt: PaymentReceipt, approved: bool, now: datetime
    ) -> None:
        if receipt.member_id is None:
            # An admin-entered receipt has no employer conversation to answer.
            return
        JobRepository.enqueue(
            db,
            kind=JobKind.RECEIPT_RESULT.value,
            payload={
                "receipt_id": str(receipt.id),
                "approved": approved,
            },
            run_at=now + timedelta(seconds=1),
            now=now,
            max_attempts=1,
            dedupe_key=f"receipt-result:{receipt.id}:{receipt.status}",
        )

    @staticmethod
    def currencies(db: Session, project_id: uuid.UUID | None = None) -> list[str]:
        stmt = select(Payment.currency).distinct()
        if project_id is not None:
            stmt = stmt.where(Payment.project_id == project_id)
        values = set(db.scalars(stmt).all())
        return sorted(values or {"IRT"})


def receipt_summary_text(receipt: PaymentReceipt, *, project_name: str) -> str:
    return (
        f"رسید پرداخت پروژه {project_name}\n"
        f"مبلغ: {format_amount(receipt.amount_minor, receipt.currency)}\n"
        f"وضعیت: {receipt.status}"
    )


def notification_type_for_receipt() -> str:
    return NotificationType.FINANCIAL.value
