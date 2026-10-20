"""Pre-sales orders: validation, persistence and the admin workflow."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import bad_request, not_found
from app.core.security import utcnow
from app.models.catalog import ServiceItem, ServiceRequest
from app.schemas.catalog import RequestUpdate
from app.services.audit import Actor, AuditService

PHONE_RE = re.compile(r"^09\d{9}$")

#: Persian and Arabic-Indic digits are common on Iranian keyboards.
DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
PERSIAN_TRANSLATION = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def normalize_digits(value: str) -> str:
    return (value or "").translate(DIGIT_TRANSLATION)


def fa_digits(value: str | int) -> str:
    """Render numbers the way the Persian UI does (۸۰۰ instead of 800)."""
    return str(value).translate(PERSIAN_TRANSLATION)


def normalize_phone(raw: str) -> str | None:
    """Accept the shapes people actually type, store one canonical form."""
    digits = re.sub(r"[\s\-()]", "", normalize_digits(raw or "").strip())
    for prefix in ("+98", "0098", "98"):
        if digits.startswith(prefix):
            digits = "0" + digits[len(prefix) :]
            break
    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    if not PHONE_RE.match(digits):
        return None
    return digits


def validate_answer(item: ServiceItem, question, raw: str) -> tuple[str | None, str | None]:
    """Return ``(value, error)`` for one answer.

    ``value`` is ``None`` for a skipped optional question.
    """
    text = (raw or "").strip()
    if not text:
        if question.required:
            return None, "پاسخ این سوال الزامی است."
        return None, None
    if len(text) > 2000:
        return None, "پاسخ طولانی تر از حد مجاز است."
    if question.field_type == "phone":
        phone = normalize_phone(text)
        if phone is None:
            return None, "شماره تماس معتبر نیست. نمونه: ۰۹۱۲۳۴۵۶۷۸۹"
        return phone, None
    if question.field_type == "number":
        normalized = normalize_digits(text).replace(",", "").replace("٬", "").replace(" ", "")
        if not normalized.isdigit():
            return None, "لطفا فقط عدد وارد کنید."
        value = int(normalized)
        if question.min_value is not None and value < question.min_value:
            return None, f"حداقل مقدار مجاز {fa_digits(question.min_value)} است."
        if question.max_value is not None and value > question.max_value:
            return None, f"حداکثر مقدار مجاز {fa_digits(question.max_value)} است."
        return str(value), None
    if question.field_type == "choice":
        options = [str(option) for option in (question.options or [])]
        if options and text not in options:
            return None, "لطفا یکی از گزینه های نمایش داده شده را انتخاب کنید."
    return text, None


class OrderService:
    @staticmethod
    def get(db: Session, request_id: uuid.UUID) -> ServiceRequest:
        request = db.get(ServiceRequest, request_id)
        if request is None:
            raise not_found("این سفارش یافت نشد.")
        return request

    @staticmethod
    def create(
        db: Session,
        *,
        category_id: uuid.UUID | None,
        item: ServiceItem,
        contact_name: str,
        contact_phone: str,
        answers: list[dict],
        telegram_user_id: uuid.UUID | None,
        telegram_username: str | None,
        telegram_id: int | None,
        actor: Actor,
    ) -> ServiceRequest:
        name = (contact_name or "").strip()
        phone = normalize_phone(contact_phone)
        if len(name) < 2:
            raise bad_request("نام و نام خانوادگی معتبر نیست.", code="invalid_name")
        if phone is None:
            raise bad_request("شماره تماس معتبر نیست.", code="invalid_phone")
        if not answers:
            raise bad_request("هیچ پاسخی ثبت نشده است.", code="empty_answers")
        now = utcnow()
        request = ServiceRequest(
            category_id=category_id,
            item_id=item.id,
            telegram_user_id=telegram_user_id,
            category_title=item.category.title,
            item_title=item.title,
            contact_name=name[:160],
            contact_phone=phone,
            answers=answers,
            status="new",
            admin_note="",
            source="telegram",
            telegram_username=telegram_username,
            telegram_id=telegram_id,
            created_at=now,
            updated_at=now,
        )
        db.add(request)
        db.flush()
        AuditService.record(
            db,
            actor=actor,
            action="order.created",
            entity_type="service_request",
            entity_id=request.id,
            context={"item": item.title, "category": item.category.title},
            now=now,
        )
        return request

    @staticmethod
    def list(
        db: Session,
        *,
        status: str | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ServiceRequest], int]:
        stmt = select(ServiceRequest)
        count_stmt = select(func.count()).select_from(ServiceRequest)
        conditions = []
        if status:
            conditions.append(ServiceRequest.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    ServiceRequest.contact_name.ilike(pattern),
                    ServiceRequest.contact_phone.ilike(pattern),
                    ServiceRequest.item_title.ilike(pattern),
                    ServiceRequest.category_title.ilike(pattern),
                )
            )
        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        total = int(db.scalar(count_stmt) or 0)
        rows = list(
            db.scalars(
                stmt.order_by(ServiceRequest.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return rows, total

    @staticmethod
    def update(
        db: Session, *, request: ServiceRequest, payload: RequestUpdate, actor: Actor
    ) -> ServiceRequest:
        now = utcnow()
        if payload.status is not None and payload.status != request.status:
            request.status = payload.status
            AuditService.record(
                db,
                actor=actor,
                action="order.status_changed",
                entity_type="service_request",
                entity_id=request.id,
                context={"status": payload.status},
                now=now,
            )
        if payload.admin_note is not None:
            request.admin_note = payload.admin_note.strip()
        request.updated_at = now
        db.flush()
        return request
