from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.messaging.base import (
    ChannelError,
    PermanentChannelError,
    TemporaryChannelError,
    UnknownChannelError,
)
from app.adapters.messaging.registry import CHANNEL_KEYS, get_channel_adapter
from app.adapters.telegram.base import TelegramAdapter
from app.adapters.telegram.formatting import html_escape, truncate
from app.core.config import get_settings
from app.core.errors import conflict, not_found
from app.core.security import utcnow
from app.domain.enums import (
    TERMINAL_NOTIFICATION_STATUSES,
    DeliveryStatus,
    JobKind,
    NotificationStatus,
    NotificationType,
)
from app.domain.notification_rules import can_cancel, can_retry
from app.models.notification import DeliveryAttempt, Notification
from app.models.project import Project
from app.models.telegram import ProjectMember
from app.models.ticket import MemberChannelIdentity
from app.repositories.jobs import JobRepository
from app.repositories.notifications import NotificationRepository
from app.repositories.projects import ProjectRepository
from app.schemas.notification import NotificationCreate
from app.services.audit import Actor, AuditService

logger = logging.getLogger(__name__)

#: Providers that understand the Telegram HTML subset used by the bot messages.
HTML_CHANNELS = frozenset({"telegram", "bale", "eitaa"})

TYPE_LABELS = {
    NotificationType.ANNOUNCEMENT.value: "اطلاعیه",
    NotificationType.FINANCIAL.value: "اطلاعیه مالی",
    NotificationType.SYSTEM.value: "اطلاعیه سیستمی",
}


class RetryableDeliveryError(Exception):
    """The worker should retry this job with backoff."""


class NotificationService:
    @staticmethod
    def format_message(notification: Notification, project: Project) -> str:
        type_label = TYPE_LABELS.get(notification.type, "اطلاعیه")
        text = (
            f"<b>{html_escape(project.name)}</b>\n"
            f"<i>{type_label}</i>\n\n"
            f"<b>{html_escape(notification.title)}</b>\n"
            f"{html_escape(notification.body)}\n\n"
            f"<i>NetNova Notify</i>"
        )
        return truncate(text)

    @staticmethod
    def create(
        db: Session,
        *,
        project: Project,
        payload: NotificationCreate,
        actor: Actor,
    ) -> Notification:
        settings = get_settings()
        now = utcnow()
        if project.status != "active":
            raise conflict("پروژه غیرفعال است و امکان ثبت اطلاعیه ندارد.")

        scheduled_at = payload.scheduled_at
        if scheduled_at is not None and scheduled_at <= now:
            scheduled_at = None

        requested_channels = [
            channel for channel in (payload.channels or ["telegram"]) if channel in CHANNEL_KEYS
        ]
        enabled_channels = {row.channel for row in project.channels if row.enabled}
        channels = [channel for channel in requested_channels if channel in enabled_channels]
        if not channels:
            raise conflict("هیچ کانال فعالی برای این پروژه انتخاب نشده است.")

        notification = Notification(
            project_id=project.id,
            type=payload.type.value,
            title=payload.title,
            body=payload.body,
            status=NotificationStatus.QUEUED.value,
            scheduled_at=scheduled_at,
            queued_at=now,
            attempt_count=0,
            created_by=actor.id if actor.type == "admin" else None,
            channels=channels,
            created_at=now,
            updated_at=now,
        )
        db.add(notification)
        db.flush()

        run_at = scheduled_at or (now + timedelta(seconds=1))
        job = JobRepository.enqueue(
            db,
            kind=JobKind.NOTIFICATION_SEND.value,
            payload={
                "notification_id": str(notification.id),
                "project_id": str(project.id),
            },
            run_at=run_at,
            now=now,
            max_attempts=settings.job_max_attempts,
            dedupe_key=f"notification-send:{notification.id}:initial",
        )
        if job is not None:
            notification.send_job_id = job.id
            db.flush()

        AuditService.record(
            db,
            actor=actor,
            action="notification.created",
            entity_type="notification",
            entity_id=notification.id,
            project_id=project.id,
            context={
                "type": notification.type,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
                "channels": channels,
                "job_id": str(job.id) if job else None,
            },
            now=now,
        )
        return notification

    @staticmethod
    def get(db: Session, notification_id) -> Notification:
        notification = NotificationRepository.get(db, notification_id)
        if notification is None:
            raise not_found("اطلاعیه یافت نشد.")
        return notification

    @staticmethod
    def cancel(db: Session, *, notification: Notification, actor: Actor) -> Notification:
        now = utcnow()
        if not can_cancel(notification.status):
            raise conflict("این اطلاعیه در وضعیت فعلی قابل لغو نیست.")
        previous_status = notification.status
        JobRepository.cancel(db, notification.send_job_id, now)
        notification.status = NotificationStatus.CANCELLED.value
        notification.cancelled_at = now
        notification.updated_at = now
        notification.last_error = None
        AuditService.record(
            db,
            actor=actor,
            action="notification.cancelled",
            entity_type="notification",
            entity_id=notification.id,
            project_id=notification.project_id,
            context={"previous_status": previous_status},
            now=now,
        )
        db.flush()
        return notification

    @staticmethod
    def request_send(db: Session, *, notification: Notification, actor: Actor) -> Notification:
        """Send a scheduled notification immediately, or retry a failed one."""
        settings = get_settings()
        now = utcnow()
        if notification.status in TERMINAL_NOTIFICATION_STATUSES:
            if not can_retry(notification.status):
                raise conflict("این اطلاعیه در وضعیت فعلی قابل ارسال دوباره نیست.")
            action = "notification.retry_requested"
        else:
            action = "notification.queued"

        project = db.get(Project, notification.project_id)
        if project is None or project.status != "active":
            raise conflict("پروژه غیرفعال است و ارسال ممکن نیست.")

        JobRepository.cancel(db, notification.send_job_id, now)
        notification.status = NotificationStatus.QUEUED.value
        notification.scheduled_at = None
        notification.queued_at = now
        notification.cancelled_at = None
        notification.last_error = None
        notification.updated_at = now
        job = JobRepository.enqueue(
            db,
            kind=JobKind.NOTIFICATION_SEND.value,
            payload={
                "notification_id": str(notification.id),
                "project_id": str(notification.project_id),
            },
            run_at=now + timedelta(seconds=1),
            now=now,
            max_attempts=settings.job_max_attempts,
            dedupe_key=f"notification-send:{notification.id}:{now.isoformat()}",
        )
        if job is not None:
            notification.send_job_id = job.id
        AuditService.record(
            db,
            actor=actor,
            action=action,
            entity_type="notification",
            entity_id=notification.id,
            project_id=notification.project_id,
            context={"previous_attempts": notification.attempt_count},
            now=now,
        )
        db.flush()
        return notification

    @staticmethod
    def mark_final_failure(db: Session, *, notification: Notification, error: str) -> None:
        if notification.status in TERMINAL_NOTIFICATION_STATUSES:
            return
        now = utcnow()
        notification.status = NotificationStatus.FAILED.value
        notification.last_error = error[:1000]
        notification.updated_at = now
        AuditService.record(
            db,
            actor=Actor(type="system", label="worker"),
            action="notification.failed",
            entity_type="notification",
            entity_id=notification.id,
            project_id=notification.project_id,
            context={"error": error[:500], "final": True},
            now=now,
        )

    # ------------------------------------------------------------------
    # Delivery (called by the worker)
    # ------------------------------------------------------------------
    @staticmethod
    def _channel_targets(
        db: Session,
        *,
        project: Project,
        channel: str,
        members: list[ProjectMember],
    ) -> list[tuple[str, str, int | None]]:
        """Resolve (channel, recipient, numeric chat id) for one provider."""
        if channel == "telegram":
            targets = []
            for member in members:
                if member.telegram_user is None:
                    continue
                chat_id = int(member.telegram_user.telegram_id)
                targets.append((channel, str(chat_id), chat_id))
            return targets

        member_ids = [member.id for member in members]
        if not member_ids:
            return []
        rows = db.scalars(
            select(MemberChannelIdentity).where(
                MemberChannelIdentity.project_id == project.id,
                MemberChannelIdentity.channel == channel,
                MemberChannelIdentity.project_member_id.in_(member_ids),
            )
        ).all()
        targets = []
        for row in rows:
            numeric: int | None = None
            if row.external_id.isdigit():
                numeric = int(row.external_id)
            targets.append((channel, row.external_id, numeric))
        return targets

    @staticmethod
    def deliver(
        db: Session,
        *,
        notification: Notification,
        adapter: TelegramAdapter | None = None,
        now: datetime | None = None,
    ) -> str:
        """Fan a notification out to every enabled channel.

        ``adapter`` is accepted for backwards compatibility with older worker
        code; channel adapters are resolved from the registry instead.
        """
        from app.services.licenses import LicenseService

        now = now or utcnow()
        if notification.status in TERMINAL_NOTIFICATION_STATUSES:
            return notification.status

        project = db.get(Project, notification.project_id)
        if project is None:
            NotificationService._fail(db, notification, "پروژه مربوط به این اطلاعیه یافت نشد.", now)
            return notification.status
        if project.status != "active" or project.archived_at is not None:
            NotificationService._fail(db, notification, "پروژه غیرفعال یا بایگانی شده است و ارسال انجام نشد.", now)
            return notification.status

        enabled_channels = [row.channel for row in project.channels if row.enabled]
        requested = [channel for channel in (notification.channels or ["telegram"]) if channel in CHANNEL_KEYS]
        channels = [channel for channel in requested if channel in enabled_channels]
        if not channels:
            NotificationService._fail(
                db,
                notification,
                "هیچ کانال فعالی برای این پروژه وجود ندارد یا کانال های انتخاب شده غیرفعال شده اند.",
                now,
            )
            return notification.status

        candidates = ProjectRepository.active_members(db, project.id)
        recipients = [
            member for member in candidates if LicenseService.assess_member(db, member, now)
        ]
        if not recipients:
            NotificationService._fail(
                db,
                notification,
                "کارفرمای متصل و تاییدشده ای برای این پروژه وجود ندارد.",
                now,
            )
            return notification.status

        targets: list[tuple[str, str, int | None]] = []
        seen_targets: set[tuple[str, str]] = set()
        for channel in channels:
            for item in NotificationService._channel_targets(
                db, project=project, channel=channel, members=recipients
            ):
                key = (item[0], item[1])
                if key not in seen_targets:
                    seen_targets.add(key)
                    targets.append(item)
        if not targets:
            NotificationService._fail(
                db,
                notification,
                "برای کانال های انتخاب شده، مقصد معتبری ثبت نشده است. شناسه کانال کارفرما را در پنل تکمیل کنید.",
                now,
            )
            return notification.status

        # A previous worker may have crashed after contacting a provider but
        # before persisting the result. Never resend to those recipients.
        unconfirmed = list(
            db.scalars(
                select(DeliveryAttempt).where(
                    DeliveryAttempt.notification_id == notification.id,
                    DeliveryAttempt.status == DeliveryStatus.SENDING.value,
                )
            ).all()
        )
        if unconfirmed:
            for attempt in unconfirmed:
                attempt.status = DeliveryStatus.UNKNOWN.value
                attempt.error = "نتیجه ارسال قبلی نامشخص است (توقف پردازش)."[:1000]
                attempt.finished_at = utcnow()
            NotificationService._fail(
                db,
                notification,
                "نتیجه ارسال قبلی نامشخص است. برای جلوگیری از ارسال تکراری، به صورت خودکار "
                "دوباره ارسال نشد. وضعیت پیام را بررسی کنید.",
                utcnow(),
            )
            return notification.status

        text = NotificationService.format_message(notification, project)
        already_sent = {
            (delivery.channel, delivery.recipient)
            for delivery in notification.deliveries
            if delivery.status == DeliveryStatus.SENT.value
        }
        pending_targets = [
            item for item in targets if (item[0], item[1]) not in already_sent
        ]

        if not pending_targets:
            notification.status = NotificationStatus.SENT.value
            notification.sent_at = notification.sent_at or now
            notification.updated_at = now
            return notification.status

        notification.status = NotificationStatus.SENDING.value
        notification.attempt_count += 1
        notification.updated_at = now
        db.flush()

        temporary_errors: list[str] = []
        permanent_errors: list[str] = []
        unknown_errors: list[str] = []

        for channel, recipient, chat_id in pending_targets:
            attempt_no = notification.attempt_count
            delivery = DeliveryAttempt(
                notification_id=notification.id,
                chat_id=chat_id,
                recipient=recipient,
                channel=channel,
                status=DeliveryStatus.SENDING.value,
                attempt_no=attempt_no,
                started_at=utcnow(),
                created_at=utcnow(),
                is_mock=False,
            )
            db.add(delivery)
            db.flush()
            # Persist the attempt marker before the network call so a crash
            # cannot cause a silent duplicate send.
            db.commit()
            try:
                if channel == "telegram" and adapter is not None:
                    from app.adapters.messaging.providers import TelegramChannelAdapter

                    channel_adapter = TelegramChannelAdapter(get_settings(), inner=adapter)
                else:
                    channel_adapter = get_channel_adapter(channel)
                if not channel_adapter.configured:
                    raise PermanentChannelError(
                        f"کانال {channel} در سرور پیکربندی نشده است."
                    )
                if channel in HTML_CHANNELS:
                    result = channel_adapter.send(recipient, text)
                else:
                    from app.adapters.messaging.providers import plain_text

                    result = channel_adapter.send_plain(recipient, plain_text(text))
                delivery.status = DeliveryStatus.SENT.value
                delivery.is_mock = result.is_mock
                if channel == "telegram" and result.message_id is not None:
                    delivery.telegram_message_id = int(result.message_id)
                    notification.telegram_message_id = int(result.message_id)
            except TemporaryChannelError as exc:
                delivery.status = DeliveryStatus.FAILED.value
                delivery.error = str(exc)[:1000]
                temporary_errors.append(str(exc))
            except UnknownChannelError as exc:
                # Never treat an unconfirmed send as success, and never auto-retry
                # it: the message may already be in the chat.
                delivery.status = DeliveryStatus.UNKNOWN.value
                delivery.error = str(exc)[:1000]
                unknown_errors.append(str(exc))
            except PermanentChannelError as exc:
                delivery.status = DeliveryStatus.FAILED.value
                delivery.error = str(exc)[:1000]
                permanent_errors.append(str(exc))
            except ChannelError as exc:  # defensive: unknown subclass
                delivery.status = DeliveryStatus.UNKNOWN.value
                delivery.error = str(exc)[:1000]
                unknown_errors.append(str(exc))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected delivery error on channel %s", channel)
                delivery.status = DeliveryStatus.UNKNOWN.value
                delivery.error = f"unexpected: {type(exc).__name__}"[:1000]
                unknown_errors.append(type(exc).__name__)
            finally:
                delivery.finished_at = utcnow()
                notification.updated_at = utcnow()
                db.flush()

        if unknown_errors:
            message = (
                "نتیجه ارسال نامشخص است و برای جلوگیری از ارسال تکراری به صورت خودکار "
                "تکرار نشد. وضعیت پیام را در کانال مربوطه بررسی و سپس در صورت نیاز دوباره ارسال کنید."
            )
            NotificationService._fail(db, notification, message, utcnow())
            return notification.status

        if not temporary_errors and not permanent_errors:
            notification.status = NotificationStatus.SENT.value
            notification.sent_at = utcnow()
            notification.last_error = None
            notification.updated_at = utcnow()
            AuditService.record(
                db,
                actor=Actor(type="system", label="worker"),
                action="notification.sent",
                entity_type="notification",
                entity_id=notification.id,
                project_id=project.id,
                context={
                    "attempt": notification.attempt_count,
                    "recipients": len(pending_targets),
                    "channels": sorted({item[0] for item in pending_targets}),
                    "telegram_message_id": notification.telegram_message_id,
                },
                now=utcnow(),
            )
            db.flush()
            return notification.status

        if temporary_errors and not permanent_errors:
            notification.status = NotificationStatus.RETRY_WAIT.value
            notification.last_error = temporary_errors[0][:1000]
            notification.updated_at = utcnow()
            db.flush()
            raise RetryableDeliveryError(temporary_errors[0])

        notification.status = NotificationStatus.FAILED.value
        notification.last_error = (permanent_errors or temporary_errors)[0][:1000]
        notification.updated_at = utcnow()
        AuditService.record(
            db,
            actor=Actor(type="system", label="worker"),
            action="notification.failed",
            entity_type="notification",
            entity_id=notification.id,
            project_id=project.id,
            context={"error": notification.last_error[:500]},
            now=utcnow(),
        )
        db.flush()
        return notification.status

    @staticmethod
    def _fail(db: Session, notification: Notification, message: str, now: datetime) -> None:
        notification.status = NotificationStatus.FAILED.value
        notification.last_error = message[:1000]
        notification.updated_at = now
        AuditService.record(
            db,
            actor=Actor(type="system", label="worker"),
            action="notification.failed",
            entity_type="notification",
            entity_id=notification.id,
            project_id=notification.project_id,
            context={"error": message[:500]},
            now=now,
        )
        db.flush()
