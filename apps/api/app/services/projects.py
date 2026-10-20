from __future__ import annotations

import re
import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.core.security import utcnow
from app.domain.enums import ChannelKey, JobKind, NotificationStatus, ProjectStatus
from app.domain.features import FEATURES
from app.models.job import ScheduledJob
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.project import Project, ProjectChannel, ProjectFeature
from app.repositories.jobs import JobRepository
from app.repositories.projects import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.audit import Actor, AuditService

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")
DEFAULT_LICENSE_DAYS = 365


class ProjectService:
    @staticmethod
    def list(
        db: Session,
        *,
        search: str | None,
        status: str | None,
        page: int,
        page_size: int,
        include_archived: bool = False,
    ) -> tuple[list[Project], int]:
        return ProjectRepository.list(
            db,
            search=search,
            status=status,
            page=page,
            page_size=page_size,
            include_archived=include_archived,
        )

    @staticmethod
    def get(db: Session, project_id: uuid.UUID) -> Project:
        project = ProjectRepository.get(db, project_id)
        if project is None:
            raise not_found("پروژه یافت نشد.")
        return project

    @staticmethod
    def _unique_slug(db: Session, slug: str) -> str:
        candidate = slug
        while ProjectRepository.get_by_slug(db, candidate) is not None:
            candidate = f"{slug[:70]}-{uuid.uuid4().hex[:5]}"
        return candidate

    @staticmethod
    def _generated_slug() -> str:
        return f"prj-{uuid.uuid4().hex[:10]}"

    @staticmethod
    def create(db: Session, *, payload: ProjectCreate, actor: Actor) -> tuple[Project, str | None]:
        from app.services.licenses import LicenseService

        now = utcnow()
        requested_slug = (payload.slug or "").strip().lower()
        if requested_slug:
            if not SLUG_RE.match(requested_slug):
                raise conflict("شناسه انگلیسی پروژه معتبر نیست.")
            if ProjectRepository.get_by_slug(db, requested_slug) is not None:
                raise conflict("این شناسه انگلیسی قبلا استفاده شده است.", code="slug_taken")
            slug = requested_slug
        else:
            slug = ProjectService._unique_slug(db, ProjectService._generated_slug())

        project = Project(
            name=payload.name,
            slug=slug,
            client_name=payload.client_name,
            description=payload.description,
            status=ProjectStatus.ACTIVE.value,
            is_demo=False,
            created_at=now,
            updated_at=now,
        )
        db.add(project)
        db.flush()

        # Feature flags: the registry is the single source of truth, so adding a
        # plugin automatically appears for new projects without a migration.
        flags = {key: definition.default_enabled for key, definition in FEATURES.items()}
        if payload.features:
            flags.update({key: value for key, value in payload.features.items() if key in FEATURES})
        for key, enabled in flags.items():
            db.add(ProjectFeature(project_id=project.id, key=key, enabled=enabled))
        db.flush()
        db.refresh(project, attribute_names=["features"])

        # Telegram is the default delivery channel; other providers are opt-in
        # per project and stay disabled until the agency configures credentials.
        db.add(
            ProjectChannel(
                project_id=project.id,
                channel=ChannelKey.TELEGRAM.value,
                enabled=True,
                settings={},
            )
        )
        for channel in (ChannelKey.BALE, ChannelKey.EITAA, ChannelKey.SMSIR):
            db.add(
                ProjectChannel(
                    project_id=project.id,
                    channel=channel.value,
                    enabled=False,
                    settings={},
                )
            )
        db.flush()
        db.refresh(project, attribute_names=["channels"])

        AuditService.record(
            db,
            actor=actor,
            action="project.created",
            entity_type="project",
            entity_id=project.id,
            project_id=project.id,
            context={"name": project.name, "slug": project.slug},
            now=now,
        )

        license_row, code = LicenseService.issue(
            db,
            project=project,
            actor=actor,
            expires_at=now + timedelta(days=DEFAULT_LICENSE_DAYS),
            reason="project_created",
            commit=False,
        )
        return project, code

    @staticmethod
    def update(
        db: Session,
        *,
        project: Project,
        payload: ProjectUpdate,
        actor: Actor,
    ) -> Project:
        now = utcnow()
        data = payload.model_dump(exclude_unset=True)
        features = data.pop("features", None)

        changed: dict[str, object] = {}
        for field, value in data.items():
            if value is None and field != "description":
                continue
            if field == "status":
                value = ProjectStatus(value).value
                if value != project.status:
                    changed["status"] = value
                    project.status = value
                    if value == ProjectStatus.INACTIVE.value:
                        ProjectService._cancel_pending_work(db, project.id, now)
                continue
            if getattr(project, field) != value:
                setattr(project, field, value)
                changed[field] = value

        if features is not None:
            unknown = set(features) - set(FEATURES)
            if unknown:
                raise conflict("قابلیت انتخاب شده وجود ندارد.")
            ProjectRepository.sync_features(db, project, features, now)
            AuditService.record(
                db,
                actor=actor,
                action="project.features_updated",
                entity_type="project",
                entity_id=project.id,
                project_id=project.id,
                context={"features": features},
                now=now,
            )

        project.updated_at = now
        if changed:
            action = (
                "project.status_changed"
                if "status" in changed and len(changed) == 1
                else "project.updated"
            )
            AuditService.record(
                db,
                actor=actor,
                action=action,
                entity_type="project",
                entity_id=project.id,
                project_id=project.id,
                context={"changed": changed},
                now=now,
            )
        db.flush()
        return project

    @staticmethod
    def _cancel_pending_work(db: Session, project_id: uuid.UUID, now) -> None:
        """Disabling a project stops queued sends and reminders immediately."""
        job_ids = list(
            db.scalars(
                select(ScheduledJob.id).where(
                    ScheduledJob.status == "pending",
                    ScheduledJob.kind.in_(
                        [
                            JobKind.NOTIFICATION_SEND.value,
                            JobKind.PAYMENT_REMINDER.value,
                            JobKind.TICKET_NOTIFY.value,
                        ]
                    ),
                    ScheduledJob.payload["project_id"].astext == str(project_id),
                )
            ).all()
        )
        for job_id in job_ids:
            JobRepository.cancel(db, job_id, now)

        db.execute(
            update(Notification)
            .where(
                Notification.project_id == project_id,
                Notification.status.in_(
                    [NotificationStatus.QUEUED.value, NotificationStatus.RETRY_WAIT.value]
                ),
            )
            .values(
                status=NotificationStatus.CANCELLED.value,
                cancelled_at=now,
                updated_at=now,
                last_error="پروژه غیرفعال شد و ارسال لغو شد.",
            )
        )
        db.execute(
            update(Payment).where(Payment.project_id == project_id).values(reminder_job_id=None)
        )


class ProjectChannelService:
    """Per-project enablement of the centrally configured providers."""

    @staticmethod
    def update(
        db: Session,
        *,
        project: Project,
        channel: str,
        payload,
        actor: Actor,
    ) -> Project:
        from app.adapters.messaging.registry import CHANNELS, channel_state

        if channel not in CHANNELS:
            raise not_found("کانال انتخاب شده وجود ندارد.")
        row = next((item for item in project.channels if item.channel == channel), None)
        if row is None:
            row = ProjectChannel(project_id=project.id, channel=channel, enabled=False, settings={})
            db.add(row)
            project.channels.append(row)
        if payload.enabled and not channel_state(channel)["configured"]:
            raise conflict(
                "این کانال هنوز در تنظیمات سرور پیکربندی نشده است و فعال سازی آن معنا ندارد."
            )
        now = utcnow()
        row.enabled = payload.enabled
        if payload.settings is not None:
            row.settings = ProjectChannelService._safe_settings(payload.settings)
        project.updated_at = now
        AuditService.record(
            db,
            actor=actor,
            action="project.channel_updated",
            entity_type="project",
            entity_id=project.id,
            project_id=project.id,
            context={"channel": channel, "enabled": payload.enabled},
            now=now,
        )
        db.flush()
        return project

    @staticmethod
    def _safe_settings(settings: dict) -> dict:
        # Only small, non-secret presentation hints are stored per project.
        allowed = {"sms_template", "signature", "reply_to"}
        cleaned: dict = {}
        for key, value in settings.items():
            if key not in allowed:
                continue
            if isinstance(value, (str, int, float, bool)):
                cleaned[key] = str(value)[:500] if isinstance(value, str) else value
        return cleaned


class ProjectLifecycleService:
    """Archive, restore and permanent deletion.

    Archiving is the normal operation: the project keeps its history, but the
    employer bot, notifications and reminders stop. Permanent deletion exists for
    demo data and genuine mistakes and is guarded by an explicit confirmation in
    the API layer.
    """

    @staticmethod
    def archive(db: Session, *, project: Project, actor: Actor) -> Project:
        if project.archived_at is not None:
            raise conflict("پروژه از قبل بایگانی شده است.")
        # Archiving also stops operation: the bot, sends and reminders all check
        # ``status``/``archived_at``. Restoring sets the project back to active.
        project.status = "inactive"
        now = utcnow()
        project.archived_at = now
        project.updated_at = now
        ProjectService._cancel_pending_work(db, project.id, now)
        AuditService.record(
            db,
            actor=actor,
            action="project.archived",
            entity_type="project",
            entity_id=project.id,
            project_id=project.id,
            now=now,
        )
        db.flush()
        return project

    @staticmethod
    def restore(db: Session, *, project: Project, actor: Actor) -> Project:
        if project.archived_at is None:
            raise conflict("پروژه بایگانی نشده است.")
        now = utcnow()
        project.archived_at = None
        project.status = "active"
        project.updated_at = now
        AuditService.record(
            db,
            actor=actor,
            action="project.restored",
            entity_type="project",
            entity_id=project.id,
            project_id=project.id,
            now=now,
        )
        db.flush()
        return project

    @staticmethod
    def delete(db: Session, *, project: Project, actor: Actor) -> None:
        now = utcnow()
        project_id = project.id
        name = project.name
        AuditService.record(
            db,
            actor=actor,
            action="project.deleted",
            entity_type="project",
            entity_id=project_id,
            project_id=project_id,
            context={"name": name, "slug": project.slug, "is_demo": project.is_demo},
            now=now,
        )
        db.flush()
        db.delete(project)
        db.flush()


def purge_demo_projects(db: Session, *, actor: Actor) -> dict:
    """Remove every project flagged ``is_demo`` (development/demo data only).

    Real projects are never touched: the flag is only set by the seed script and
    by explicit admin action, and every deletion is audited individually.
    """
    demo_projects = ProjectRepository.demo_projects(db)
    details = []
    for project in demo_projects:
        details.append({"id": str(project.id), "name": project.name})
        ProjectLifecycleService.delete(db, project=project, actor=actor)
    AuditService.record(
        db,
        actor=actor,
        action="project.demo_purged",
        entity_type="system",
        entity_id=None,
        context={"count": len(details)},
        now=utcnow(),
    )
    db.flush()
    return {"deleted": len(details), "projects": details}


class MemberChannelService:
    """Destinations for non-Telegram providers, per project member.

    Telegram identity is owned by the bot; other providers need an explicit target
    (Bale/Eitaa chat id or a mobile number). Uniqueness prevents two members from
    sharing a destination by accident.
    """

    @staticmethod
    def list_for_member(db: Session, member_id: uuid.UUID) -> list:
        from app.models.ticket import MemberChannelIdentity

        return list(
            db.scalars(
                select(MemberChannelIdentity)
                .where(MemberChannelIdentity.project_member_id == member_id)
                .order_by(MemberChannelIdentity.channel)
            ).all()
        )

    @staticmethod
    def _validate(channel: str, external_id: str) -> str:
        from app.adapters.messaging.registry import CHANNELS

        if channel not in CHANNELS or channel == "telegram":
            raise not_found("کانال انتخاب شده پشتیبانی نمی شود.")
        value = (external_id or "").strip()
        if channel == "smsir":
            digits = value.replace(" ", "").replace("-", "")
            if not re.fullmatch(r"09\d{9}", digits):
                raise conflict("شماره موبایل باید به شکل 09xxxxxxxxx باشد.")
            return digits
        if not re.fullmatch(r"-?\d{3,20}", value):
            raise conflict("شناسه چت باید عددی باشد.")
        return value

    @staticmethod
    def upsert(
        db: Session,
        *,
        member,
        channel: str,
        external_id: str,
        label: str | None,
        actor: Actor,
    ):
        from app.models.ticket import MemberChannelIdentity

        value = MemberChannelService._validate(channel, external_id)
        existing = db.scalar(
            select(MemberChannelIdentity).where(
                MemberChannelIdentity.project_member_id == member.id,
                MemberChannelIdentity.channel == channel,
            )
        )
        duplicate = db.scalar(
            select(MemberChannelIdentity).where(
                MemberChannelIdentity.channel == channel,
                MemberChannelIdentity.external_id == value,
                MemberChannelIdentity.project_member_id != member.id,
            )
        )
        if duplicate is not None:
            raise conflict("این مقصد قبلا برای عضو دیگری ثبت شده است.")
        now = utcnow()
        if existing is None:
            existing = MemberChannelIdentity(
                project_id=member.project_id,
                project_member_id=member.id,
                channel=channel,
                external_id=value,
                label=(label or None),
            )
            db.add(existing)
        else:
            existing.external_id = value
            existing.label = label or None
        AuditService.record(
            db,
            actor=actor,
            action="member.channel_saved",
            entity_type="project_member",
            entity_id=member.id,
            project_id=member.project_id,
            context={"channel": channel},
            now=now,
        )
        db.flush()
        return existing

    @staticmethod
    def delete(db: Session, *, member, channel: str, actor: Actor) -> None:
        from app.models.ticket import MemberChannelIdentity

        row = db.scalar(
            select(MemberChannelIdentity).where(
                MemberChannelIdentity.project_member_id == member.id,
                MemberChannelIdentity.channel == channel,
            )
        )
        if row is None:
            raise not_found("مقصدی برای این کانال ثبت نشده است.")
        db.delete(row)
        AuditService.record(
            db,
            actor=actor,
            action="member.channel_removed",
            entity_type="project_member",
            entity_id=member.id,
            project_id=member.project_id,
            context={"channel": channel},
            now=utcnow(),
        )
        db.flush()
