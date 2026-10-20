from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.core.errors import bad_request, not_found
from app.db.session import get_db
from app.domain.attachments import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS_PER_MESSAGE,
    AttachmentInput,
)
from app.domain.enums import ReceiptStatus
from app.domain.message_templates import DEFAULTS
from app.domain.payments import format_amount
from app.models.accounting import PaymentMethod, PaymentReceiptFile
from app.schemas.accounting import (
    AccountingOverviewOut,
    AllocationUpdate,
    MessageTemplateIn,
    MessageTemplateOut,
    PaymentMethodIn,
    PaymentMethodOut,
    ReceiptCreate,
    ReceiptOut,
    ReceiptReview,
)
from app.services.accounting import (
    AccountingService,
    PaymentMethodService,
    TemplateService,
    template_output,
)
from app.services.projects import ProjectService

router = APIRouter(prefix="/accounting", tags=["accounting"])


def _receipt_out(db: Session, receipt, *, project_name: str | None = None) -> ReceiptOut:
    if project_name is None:
        project = ProjectService.get(db, receipt.project_id)
        project_name = project.name
    return AccountingService.receipt_out(receipt, project_name=project_name)


# ---------------------------------------------------------------------------
# Overview / totals
# ---------------------------------------------------------------------------
@router.get("/overview", response_model=AccountingOverviewOut)
def accounting_overview(
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> AccountingOverviewOut:
    return AccountingService.overview(db)


@router.get("/projects/{project_id}/totals", response_model=AccountingOverviewOut)
def project_totals(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> AccountingOverviewOut:
    project = ProjectService.get(db, project_id)
    totals = AccountingService.project_totals(db, project.id)
    pending = AccountingService.pending_receipts(db, project.id)
    from app.schemas.accounting import CurrencyTotalsOut, ProjectAccountingOut

    return AccountingOverviewOut(
        totals=[
            CurrencyTotalsOut(
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
            for total in totals
        ],
        projects=[
            ProjectAccountingOut(
                project_id=project.id,
                project_name=project.name,
                totals=[
                    CurrencyTotalsOut(
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
                    for total in totals
                ],
            )
        ],
    )


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------
@router.get("/receipts", response_model=list[ReceiptOut])
def list_receipts(
    project_id: uuid.UUID | None = Query(default=None),
    receipt_status: ReceiptStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> list[ReceiptOut]:
    rows = AccountingService.list_receipts(
        db,
        project_id=project_id,
        status=receipt_status.value if receipt_status else None,
        limit=limit,
    )
    projects = {}
    output = []
    for receipt in rows:
        if receipt.project_id not in projects:
            projects[receipt.project_id] = ProjectService.get(db, receipt.project_id).name
        output.append(AccountingService.receipt_out(receipt, project_name=projects[receipt.project_id]))
    return output


@router.get("/receipts/{receipt_id}", response_model=ReceiptOut)
def get_receipt(
    receipt_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> ReceiptOut:
    return _receipt_out(db, AccountingService.get_receipt(db, receipt_id))


@router.post("/projects/{project_id}/receipts", response_model=ReceiptOut, status_code=201)
def create_receipt(
    project_id: uuid.UUID,
    payload: ReceiptCreate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ReceiptOut:
    project = ProjectService.get(db, project_id)
    receipt = AccountingService.create_receipt(
        db,
        project=project,
        actor=ctx.actor,
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        tracking_code=payload.tracking_code,
        note=payload.note,
        channel="web",
        submitted_by_type="admin",
    )
    return _receipt_out(db, receipt, project_name=project.name)


@router.post("/receipts/{receipt_id}/files", response_model=ReceiptOut)
async def add_receipt_files(
    receipt_id: uuid.UUID,
    files: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> ReceiptOut:
    uploads = files or []
    if not uploads:
        raise bad_request("حداقل یک تصویر انتخاب کنید.", code="no_attachment")
    if len(uploads) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise bad_request(
            f"حداکثر {MAX_ATTACHMENTS_PER_MESSAGE} تصویر برای هر رسید مجاز است.",
            code="too_many_attachments",
        )
    receipt = AccountingService.get_receipt(db, receipt_id)
    drafts = [
        AttachmentInput(
            data=await upload.read(MAX_ATTACHMENT_BYTES + 1),
            filename=upload.filename or "image",
            content_type=upload.content_type,
        )
        for upload in uploads
    ]
    prepared = AccountingService._prepare_files(drafts)
    AccountingService._store_files(db, receipt=receipt, prepared=prepared, now=receipt.updated_at)
    db.commit()
    return _receipt_out(db, AccountingService.get_receipt(db, receipt_id))


@router.get("/receipt-files/{file_id}")
def download_receipt_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> Response:
    row = db.get(PaymentReceiptFile, file_id)
    if row is None:
        raise not_found("تصویر رسید یافت نشد.")
    return Response(
        content=row.data,
        media_type=row.content_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(row.filename)}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/receipts/{receipt_id}/approve", response_model=ReceiptOut)
def approve_receipt(
    receipt_id: uuid.UUID,
    payload: ReceiptReview | None = None,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ReceiptOut:
    receipt = AccountingService.get_receipt(db, receipt_id)
    AccountingService.approve(
        db,
        receipt=receipt,
        actor=ctx.actor,
        allocations=payload.allocations if payload else None,
        note=payload.note if payload else "",
    )
    db.commit()
    return _receipt_out(db, AccountingService.get_receipt(db, receipt_id))


@router.post("/receipts/{receipt_id}/reject", response_model=ReceiptOut)
def reject_receipt(
    receipt_id: uuid.UUID,
    payload: ReceiptReview,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ReceiptOut:
    receipt = AccountingService.get_receipt(db, receipt_id)
    AccountingService.reject(db, receipt=receipt, actor=ctx.actor, reason=payload.note)
    db.commit()
    return _receipt_out(db, AccountingService.get_receipt(db, receipt_id))


@router.patch("/receipts/{receipt_id}/allocations", response_model=ReceiptOut)
def update_allocations(
    receipt_id: uuid.UUID,
    payload: AllocationUpdate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ReceiptOut:
    receipt = AccountingService.get_receipt(db, receipt_id)
    AccountingService.replace_allocations(
        db, receipt=receipt, allocations=payload.allocations, actor=ctx.actor
    )
    db.commit()
    return _receipt_out(db, AccountingService.get_receipt(db, receipt_id))


@router.get("/receipts/{receipt_id}/summary")
def receipt_summary(
    receipt_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> dict:
    receipt = AccountingService.get_receipt(db, receipt_id)
    return {
        "amount": format_amount(receipt.amount_minor, receipt.currency),
        "status": receipt.status,
        "files": len(receipt.files),
        "allocated": sum(item.amount_minor for item in receipt.allocations),
    }


# ---------------------------------------------------------------------------
# Payment methods
# ---------------------------------------------------------------------------
@router.get("/payment-methods", response_model=list[PaymentMethodOut])
def list_payment_methods(
    project_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> list[PaymentMethodOut]:
    rows = PaymentMethodService.list(db, project_id=project_id)
    return [PaymentMethodOut.model_validate(row, from_attributes=True) for row in rows]


@router.post("/payment-methods", response_model=PaymentMethodOut, status_code=201)
def create_payment_method(
    payload: PaymentMethodIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> PaymentMethodOut:
    if payload.project_id is not None:
        ProjectService.get(db, payload.project_id)
    row = PaymentMethodService.create(db, payload=payload, actor=ctx.actor)
    db.commit()
    return PaymentMethodOut.model_validate(row, from_attributes=True)


@router.patch("/payment-methods/{method_id}", response_model=PaymentMethodOut)
def update_payment_method(
    method_id: uuid.UUID,
    payload: PaymentMethodIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> PaymentMethodOut:
    row = PaymentMethodService.get(db, method_id)
    if payload.project_id is not None:
        ProjectService.get(db, payload.project_id)
    PaymentMethodService.update(db, row=row, payload=payload, actor=ctx.actor)
    db.commit()
    return PaymentMethodOut.model_validate(row, from_attributes=True)


@router.delete("/payment-methods/{method_id}", status_code=204)
def delete_payment_method(
    method_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> Response:
    row: PaymentMethod = PaymentMethodService.get(db, method_id)
    PaymentMethodService.delete(db, row=row, actor=ctx.actor)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------
@router.get("/templates", response_model=list[MessageTemplateOut])
def list_templates(
    project_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> list[MessageTemplateOut]:
    if project_id is not None:
        ProjectService.get(db, project_id)
    return TemplateService.list(db, project_id=project_id)


@router.put("/templates/{key}", response_model=MessageTemplateOut)
def update_template(
    key: str,
    payload: MessageTemplateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> MessageTemplateOut:
    if key not in DEFAULTS:
        raise not_found("متن آماده یافت نشد.")
    if payload.project_id is not None:
        ProjectService.get(db, payload.project_id)
    result = TemplateService.upsert(
        db, key=key, body=payload.body, project_id=payload.project_id, actor=ctx.actor
    )
    db.commit()
    return result


@router.delete("/templates/{key}", response_model=MessageTemplateOut)
def reset_template(
    key: str,
    project_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> MessageTemplateOut:
    if key not in DEFAULTS:
        raise not_found("متن آماده یافت نشد.")
    result = TemplateService.reset(db, key=key, project_id=project_id, actor=ctx.actor)
    db.commit()
    return result


__all__ = ["router", "template_output"]
