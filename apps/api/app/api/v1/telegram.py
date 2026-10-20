from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.adapters.telegram.factory import get_telegram_adapter
from app.core.config import get_settings
from app.core.errors import ApiError, bad_request, forbidden
from app.core.rate_limit import rate_limiter
from app.core.security import compare_tokens, utcnow
from app.db.session import get_db
from app.models.telegram import TelegramUpdate
from app.schemas.member import ActivationRequest, ActivationResult
from app.schemas.telegram import TelegramUpdatePayload, TelegramWebhookResponse
from app.services.licenses import LicenseService
from app.services.telegram_bot import TelegramBotService

router = APIRouter(tags=["telegram"])


def _verify_bot_secret(request: Request) -> None:
    settings = get_settings()
    provided = request.headers.get("x-telegram-bot-api-secret-token", "")
    if settings.telegram_webhook_secret:
        if not compare_tokens(provided, settings.telegram_webhook_secret):
            raise forbidden("درخواست تلگرام معتبر نیست.")
        return
    if settings.environment == "production":
        raise ApiError(
            503,
            "webhook_secret_missing",
            "Secret وب هوک تلگرام تنظیم نشده است.",
        )


@router.post("/telegram/webhook", response_model=TelegramWebhookResponse)
def telegram_webhook(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
) -> TelegramWebhookResponse:
    settings = get_settings()
    _verify_bot_secret(request)

    try:
        update = TelegramUpdatePayload.model_validate(payload)
    except ValidationError as exc:
        raise bad_request("ساختار به روزرسانی تلگرام معتبر نیست.", code="invalid_update") from exc

    now = utcnow()
    insert_stmt = (
        pg_insert(TelegramUpdate)
        .values(
            id=uuid.uuid4(),
            update_id=update.update_id,
            received_at=now,
            processed=False,
        )
        .on_conflict_do_nothing(index_elements=["update_id"])
        .returning(TelegramUpdate.id)
    )
    db.scalar(insert_stmt)
    db.commit()

    row = db.scalar(
        select(TelegramUpdate).where(TelegramUpdate.update_id == update.update_id).with_for_update()
    )
    if row is None:
        raise ApiError(500, "update_persist_failed", "ثبت به روزرسانی تلگرام ممکن نشد.")
    if row.processed:
        return TelegramWebhookResponse(duplicate=True)

    try:
        TelegramBotService(db, get_telegram_adapter(), settings).handle_update(payload)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        failed_row = db.scalar(
            select(TelegramUpdate).where(TelegramUpdate.update_id == update.update_id)
        )
        if failed_row is not None:
            failed_row.error = f"{type(exc).__name__}: {str(exc)[:400]}"
            db.commit()
        raise ApiError(
            500,
            "webhook_processing_failed",
            "پردازش به روزرسانی تلگرام ناموفق بود.",
        ) from exc

    row.processed = True
    row.error = None
    db.commit()
    return TelegramWebhookResponse()


@router.post("/licenses/activate", response_model=ActivationResult)
def activate_license(
    request: Request,
    payload: ActivationRequest,
    db: Session = Depends(get_db),
) -> ActivationResult:
    """Activation endpoint for a bot process that is deployed separately.

    The central bot in this repository calls the service in-process. This
    endpoint is protected with the Telegram webhook secret; the destination and
    project are always derived from the license on the server.
    """
    settings = get_settings()
    _verify_bot_secret(request)
    if not rate_limiter.allow(
        f"activation:{payload.telegram_id}", settings.activation_rate_limit, 60
    ):
        raise ApiError(
            429,
            "rate_limited",
            "تعداد تلاش های فعال سازی بیش از حد مجاز است. یک دقیقه بعد دوباره تلاش کنید.",
        )

    user = LicenseService.create_or_get_telegram_user(
        db,
        telegram_id=payload.telegram_id,
        username=payload.username,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    return LicenseService.activate(db, code=payload.code, telegram_user=user)
