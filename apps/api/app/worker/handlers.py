from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.adapters.telegram.base import (
    PermanentTelegramError,
    TelegramAdapter,
    UnknownTelegramError,
)
from app.core.config import Settings
from app.models.job import ScheduledJob
from app.repositories.licenses import MemberRepository
from app.repositories.notifications import NotificationRepository
from app.services.licenses import LicenseService
from app.services.notifications import NotificationService
from app.services.payments import PaymentService
from app.services.telegram_bot import TelegramBotService

logger = logging.getLogger(__name__)


def handle_notification_send(
    db: Session, job: ScheduledJob, adapter: TelegramAdapter, settings: Settings
) -> None:
    raw_id = job.payload.get("notification_id")
    if not raw_id:
        logger.warning("notification_send job %s has no notification_id", job.id)
        return
    notification = NotificationRepository.get(db, uuid.UUID(str(raw_id)), lock=True)
    if notification is None:
        logger.warning("notification %s not found for job %s", raw_id, job.id)
        return
    NotificationService.deliver(db, notification=notification, adapter=adapter)


def handle_payment_reminder(
    db: Session, job: ScheduledJob, adapter: TelegramAdapter, settings: Settings
) -> None:
    PaymentService.handle_reminder(db, job, adapter)


def handle_activation_approved(
    db: Session, job: ScheduledJob, adapter: TelegramAdapter, settings: Settings
) -> None:
    raw_id = job.payload.get("member_id")
    if not raw_id:
        return
    member = MemberRepository.get(db, uuid.UUID(str(raw_id)))
    if member is None or member.status != "active":
        return
    if not LicenseService.assess_member(db, member):
        logger.info("Approval welcome skipped: member %s no longer has access", member.id)
        return
    chat_id = int(job.payload.get("chat_id") or member.telegram_user.telegram_id)
    try:
        TelegramBotService.send_approval_welcome(
            db, adapter, settings, member=member, chat_id=chat_id
        )
    except UnknownTelegramError as exc:
        # Do not retry: the message may already have been delivered.
        job.last_error = (
            "نتیجه ارسال پیام خوش آمدگویی نامشخص است و برای جلوگیری از ارسال تکراری "
            f"تکرار نشد: {exc}"
        )[:1000]
        logger.warning("Unknown outcome for approval welcome to chat %s", chat_id)
    except PermanentTelegramError as exc:
        job.last_error = f"ارسال پیام خوش آمدگویی ممکن نشد: {exc}"[:1000]
        logger.warning("Permanent failure for approval welcome to chat %s", chat_id)


def handle_ticket_notify(
    db: Session, job: ScheduledJob, adapter: TelegramAdapter, settings: Settings
) -> None:
    """Send a short alert about a new ticket message.

    The full thread stays in the panel; the chat message only carries a subject,
    a one-line preview and a pointer to the bot's ticket list.
    """
    from app.models.ticket import Ticket, TicketMessage
    from app.services.tickets import clean_for_telegram

    raw_ticket = job.payload.get("ticket_id")
    raw_message = job.payload.get("message_id")
    if not raw_ticket or not raw_message:
        logger.warning("ticket_notify job %s is missing identifiers", job.id)
        return
    ticket = db.get(Ticket, uuid.UUID(str(raw_ticket)))
    message = db.get(TicketMessage, uuid.UUID(str(raw_message)))
    if ticket is None or message is None:
        logger.info("ticket %s no longer exists; notification skipped", raw_ticket)
        return
    project = ticket.project
    preview = clean_for_telegram(message.body)

    if job.payload.get("target") == "admin":
        if not settings.admin_telegram_chat_id:
            return
        who = "کارفرما" if message.author_type == "employer" else "مدیر"
        text = (
            "<b>تیکت جدید / پاسخ کارفرما</b>\n"
            f"پروژه: {project.name if project else '-'}\n"
            f"موضوع: {ticket.subject}\n"
            f"از طرف: {who}\n\n"
            f"{preview}\n\n"
            "برای پاسخ به پنل مدیریت مراجعه کنید."
        )
        adapter.send_message(settings.admin_telegram_chat_id, text)
        return

    member_id = job.payload.get("member_id")
    member = MemberRepository.get(db, uuid.UUID(str(member_id))) if member_id else None
    if member is None or member.status != "active" or member.telegram_user is None:
        logger.info("Ticket notice skipped: employer is not active")
        return
    if member.project is not None and member.project.archived_at is not None:
        return
    chat_id = int(member.telegram_user.telegram_id)
    memberships = LicenseService.access_memberships(db, member.telegram_user)
    index = next(
        (position for position, item in enumerate(memberships) if item.id == member.id), None
    )
    from app.adapters.telegram.formatting import inline_keyboard

    if index is None:
        rows = [[("راهنما", "help")]]
    else:
        rows = [
            [("مشاهده تیکت ها", f"{index}:tickets")],
            [("بازگشت به منو", f"{index}:home")],
        ]
    text = f"<b>پاسخ جدید پشتیبانی</b>\nموضوع: {ticket.subject}\n\n{preview}"
    adapter.send_message(chat_id, text, inline_keyboard(rows))


HANDLERS = {
    "notification_send": handle_notification_send,
    "payment_reminder": handle_payment_reminder,
    "activation_approved": handle_activation_approved,
    "ticket_notify": handle_ticket_notify,
}


def finalize_notification_failure(db: Session, job: ScheduledJob, error: str) -> None:
    raw_id = job.payload.get("notification_id")
    if not raw_id:
        return
    notification = NotificationRepository.get(db, uuid.UUID(str(raw_id)))
    if notification is None:
        return
    NotificationService.mark_final_failure(db, notification=notification, error=error)
