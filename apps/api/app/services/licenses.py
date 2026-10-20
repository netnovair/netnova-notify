from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError, conflict, not_found
from app.core.security import (
    generate_license_code,
    hash_license_code,
    license_prefix,
    normalize_license_code,
    utcnow,
)
from app.domain.enums import JobKind, LicenseStatus, MemberStatus
from app.domain.licenses import effective_status, is_usable, should_auto_expire
from app.models.job import ScheduledJob
from app.models.license import License
from app.models.project import Project
from app.models.telegram import ProjectMember, TelegramUser
from app.repositories.jobs import JobRepository
from app.repositories.licenses import LicenseRepository, MemberRepository
from app.repositories.users import TelegramUserRepository
from app.schemas.member import ActivationResult
from app.services.audit import SYSTEM_ACTOR, Actor, AuditService

logger = logging.getLogger(__name__)

# MVP policy: one verified employer per project. The schema already supports
# multiple members; raising this limit is a configuration change, not a rewrite.
MAX_MEMBERS_PER_PROJECT = 1
MEMBER_ACTIVE_STATUSES = (MemberStatus.PENDING_APPROVAL.value, MemberStatus.ACTIVE.value)


class LicenseService:
    @staticmethod
    def issue(
        db: Session,
        *,
        project: Project,
        actor: Actor,
        expires_at: datetime | None,
        reason: str,
        commit: bool = False,
    ) -> tuple[License, str]:
        settings = get_settings()
        now = utcnow()
        if expires_at is not None and expires_at <= now:
            raise conflict("تاریخ انقضای لایسنس باید در آینده باشد.", code="invalid_expiry")

        live = LicenseRepository.live_for_project(db, project.id)
        old_ids = [license_row.id for license_row in live]
        for license_row in live:
            license_row.status = LicenseStatus.REVOKED.value
            license_row.revoked_at = now
            license_row.updated_at = now
        if live:
            db.flush()

        raw_code = ""
        code_hash = ""
        for _ in range(5):
            candidate = generate_license_code()
            candidate_hash = hash_license_code(candidate, settings.secret_key)
            if LicenseRepository.by_code_hash(db, candidate_hash) is None:
                raw_code, code_hash = candidate, candidate_hash
                break
        if not raw_code:
            raise ApiError(
                500, "license_generation_failed", "صدور لایسنس ممکن نشد. دوباره تلاش کنید."
            )

        license_row = License(
            project_id=project.id,
            code_hash=code_hash,
            code_prefix=license_prefix(raw_code),
            status=LicenseStatus.PENDING.value,
            expires_at=expires_at,
            issued_by=actor.id if actor.type == "admin" else None,
            created_at=now,
            updated_at=now,
        )
        db.add(license_row)
        db.flush()

        if old_ids:
            # Renewal must not disconnect the current employer: rebind members to
            # the new license instead of revoking them.
            db.execute(
                update(ProjectMember)
                .where(ProjectMember.license_id.in_(old_ids))
                .values(license_id=license_row.id)
            )

        AuditService.record(
            db,
            actor=actor,
            action="license.issued",
            entity_type="license",
            entity_id=license_row.id,
            project_id=project.id,
            context={"prefix": license_row.code_prefix, "reason": reason},
            now=now,
        )
        if commit:
            db.commit()
        return license_row, raw_code

    @staticmethod
    def revoke(db: Session, *, license_row: License, actor: Actor, reason: str) -> int:
        now = utcnow()
        if license_row.status == LicenseStatus.REVOKED.value:
            return 0
        license_row.status = LicenseStatus.REVOKED.value
        license_row.revoked_at = now
        license_row.updated_at = now
        members = list(
            db.scalars(
                select(ProjectMember).where(
                    ProjectMember.license_id == license_row.id,
                    ProjectMember.status.in_(MEMBER_ACTIVE_STATUSES),
                )
            ).all()
        )
        for member in members:
            member.status = MemberStatus.REVOKED.value
            member.revoked_at = now
            member.updated_at = now
        db.flush()
        AuditService.record(
            db,
            actor=actor,
            action="license.revoked",
            entity_type="license",
            entity_id=license_row.id,
            project_id=license_row.project_id,
            context={
                "prefix": license_row.code_prefix,
                "reason": reason,
                "members_revoked": len(members),
            },
            now=now,
        )
        return len(members)

    @staticmethod
    def enforce_expiry(db: Session, license_row: License, now: datetime | None = None) -> bool:
        """Persist the expired state and drop access. Returns True if changed."""
        now = now or utcnow()
        if not should_auto_expire(license_row.status, license_row.expires_at, now):
            return False
        license_row.status = LicenseStatus.EXPIRED.value
        license_row.updated_at = now
        members = list(
            db.scalars(
                select(ProjectMember).where(
                    ProjectMember.license_id == license_row.id,
                    ProjectMember.status.in_(MEMBER_ACTIVE_STATUSES),
                )
            ).all()
        )
        for member in members:
            member.status = MemberStatus.REVOKED.value
            member.revoked_at = now
            member.updated_at = now
        db.flush()
        AuditService.record(
            db,
            actor=SYSTEM_ACTOR,
            action="license.expired",
            entity_type="license",
            entity_id=license_row.id,
            project_id=license_row.project_id,
            context={"prefix": license_row.code_prefix, "members_revoked": len(members)},
            now=now,
        )
        return True

    @staticmethod
    def get(db: Session, license_id: uuid.UUID) -> License:
        license_row = LicenseRepository.get(db, license_id, lock=True)
        if license_row is None:
            raise not_found("لایسنس یافت نشد.")
        LicenseService.enforce_expiry(db, license_row)
        return license_row

    @staticmethod
    def list_for_project(db: Session, project_id: uuid.UUID) -> list[License]:
        LicenseService.enforce_expiry_for_project(db, project_id)
        return LicenseRepository.list_for_project(db, project_id)

    @staticmethod
    def live_for_project(db: Session, project_id: uuid.UUID) -> License | None:
        LicenseService.enforce_expiry_for_project(db, project_id)
        live = LicenseRepository.live_for_project(db, project_id)
        return live[0] if live else None

    @staticmethod
    def expire_all_due(db: Session, now: datetime | None = None) -> int:
        now = now or utcnow()
        changed = 0
        for license_row in LicenseRepository.live_due_for_expiry(db, now):
            if LicenseService.enforce_expiry(db, license_row, now):
                changed += 1
        return changed

    @staticmethod
    def enforce_expiry_for_project(db: Session, project_id: uuid.UUID) -> None:
        now = utcnow()
        for license_row in LicenseRepository.live_for_project(db, project_id):
            LicenseService.enforce_expiry(db, license_row, now)

    # ------------------------------------------------------------------
    # Activation and access control
    # ------------------------------------------------------------------
    @staticmethod
    def activate(
        db: Session,
        *,
        code: str,
        telegram_user: TelegramUser,
    ) -> ActivationResult:
        settings = get_settings()
        now = utcnow()
        normalized = normalize_license_code(code)
        generic_error = ApiError(
            400,
            "invalid_license",
            "کد لایسنس معتبر نیست. کد را بررسی و دوباره ارسال کنید.",
        )
        if len(normalized) < 12:
            raise generic_error

        code_hash = hash_license_code(code, settings.secret_key)
        license_row = LicenseRepository.by_code_hash(db, code_hash, lock=True)
        if license_row is None:
            raise generic_error

        LicenseService.enforce_expiry(db, license_row, now)
        if license_row.status == LicenseStatus.REVOKED.value:
            raise ApiError(400, "license_revoked", "این کد لایسنس لغو شده و قابل استفاده نیست.")
        if license_row.status == LicenseStatus.EXPIRED.value:
            raise ApiError(400, "license_expired", "مدت اعتبار این لایسنس به پایان رسیده است.")
        if license_row.status not in (LicenseStatus.PENDING.value, LicenseStatus.ACTIVE.value):
            raise generic_error

        project = db.get(Project, license_row.project_id)
        if project is None or project.status != "active":
            raise ApiError(400, "project_inactive", "پروژه مربوط به این لایسنس فعال نیست.")

        membership = MemberRepository.find(
            db, project_id=project.id, telegram_user_id=telegram_user.id
        )
        if membership is not None and membership.status == MemberStatus.ACTIVE.value:
            return ActivationResult(
                status="active",
                membership_status=membership.status,
                project_id=project.id,
                project_name=project.name,
                message="اتصال شما به این پروژه از قبل فعال است.",
                already_active=True,
            )
        if membership is not None and membership.status == MemberStatus.PENDING_APPROVAL.value:
            return ActivationResult(
                status="pending",
                membership_status=membership.status,
                project_id=project.id,
                project_name=project.name,
                message="درخواست شما ثبت شده و در انتظار تایید مدیر است.",
            )

        others = list(
            db.scalars(
                select(ProjectMember).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.status.in_(MEMBER_ACTIVE_STATUSES),
                    ProjectMember.telegram_user_id != telegram_user.id,
                )
            ).all()
        )
        if len(others) >= MAX_MEMBERS_PER_PROJECT:
            raise ApiError(
                409,
                "license_in_use",
                "این لایسنس قبلا به کارفرمای دیگری متصل شده است. برای تغییر کارفرما با مدیر تماس بگیرید.",
            )

        if membership is None:
            membership = ProjectMember(
                project_id=project.id,
                telegram_user_id=telegram_user.id,
                license_id=license_row.id,
                role="owner",
                status=MemberStatus.PENDING_APPROVAL.value,
                created_at=now,
                updated_at=now,
            )
            db.add(membership)
        else:
            # A previously revoked member may request access again with a valid code.
            membership.status = MemberStatus.PENDING_APPROVAL.value
            membership.license_id = license_row.id
            membership.revoked_at = None
            membership.activated_at = None
            membership.updated_at = now

        if license_row.status == LicenseStatus.PENDING.value:
            license_row.status = LicenseStatus.ACTIVE.value
            license_row.activated_at = now
            license_row.updated_at = now
            AuditService.record(
                db,
                actor=Actor(
                    type="telegram_user",
                    id=telegram_user.id,
                    label=telegram_user.username or str(telegram_user.telegram_id),
                ),
                action="license.activated",
                entity_type="license",
                entity_id=license_row.id,
                project_id=project.id,
                context={"prefix": license_row.code_prefix},
                now=now,
            )

        db.flush()
        AuditService.record(
            db,
            actor=Actor(
                type="telegram_user",
                id=telegram_user.id,
                label=telegram_user.username or str(telegram_user.telegram_id),
            ),
            action="member.activation_requested",
            entity_type="project_member",
            entity_id=membership.id,
            project_id=project.id,
            context={
                "project": project.name,
                "telegram_id": telegram_user.telegram_id,
                "license_prefix": license_row.code_prefix,
            },
            now=now,
        )
        return ActivationResult(
            status="pending",
            membership_status=membership.status,
            project_id=project.id,
            project_name=project.name,
            message="درخواست اتصال شما ثبت شد و پس از تایید مدیر فعال می شود.",
        )

    @staticmethod
    def access_memberships(db: Session, telegram_user: TelegramUser) -> list[ProjectMember]:
        """Freshly evaluated access list for the bot (never trust callback data)."""
        now = utcnow()
        memberships = MemberRepository.memberships_for_user(db, telegram_user.id)
        result: list[ProjectMember] = []
        for member in memberships:
            if member.status != MemberStatus.ACTIVE.value:
                continue
            license_row = member.license
            if license_row is not None and LicenseService.enforce_expiry(db, license_row, now):
                continue
            if member.status != MemberStatus.ACTIVE.value:
                continue
            if member.project.status != "active":
                continue
            if license_row is None or not is_usable(
                license_row.status, license_row.expires_at, True, now
            ):
                continue
            result.append(member)
        return result

    @staticmethod
    def assess_member(db: Session, member: ProjectMember, now: datetime | None = None) -> bool:
        now = now or utcnow()
        if member.status != MemberStatus.ACTIVE.value:
            return False
        if member.project.status != "active":
            return False
        if member.license is None:
            return False
        if LicenseService.enforce_expiry(db, member.license, now):
            return False
        return member.license.status == LicenseStatus.ACTIVE.value

    @staticmethod
    def effective(license_row: License, now: datetime | None = None) -> str:
        return effective_status(license_row.status, license_row.expires_at, now or utcnow())

    # ------------------------------------------------------------------
    # Membership decisions (admin)
    # ------------------------------------------------------------------
    @staticmethod
    def approve_member(db: Session, *, member: ProjectMember, actor: Actor) -> ProjectMember:
        now = utcnow()
        if member.status == MemberStatus.ACTIVE.value:
            return member
        if member.status != MemberStatus.PENDING_APPROVAL.value:
            raise conflict("این درخواست در وضعیت قابل تایید نیست.")
        if member.project.status != "active":
            raise conflict("پروژه غیرفعال است و تایید اتصال ممکن نیست.")
        license_row = member.license
        if license_row is None:
            raise conflict("لایسنس مرتبط با این درخواست یافت نشد.")
        LicenseService.enforce_expiry(db, license_row, now)
        if license_row.status not in (LicenseStatus.ACTIVE.value,):
            raise conflict("لایسنس این درخواست معتبر نیست.")

        member.status = MemberStatus.ACTIVE.value
        member.activated_at = now
        member.revoked_at = None
        member.updated_at = now
        if member.project.telegram_connected_at is None:
            member.project.telegram_connected_at = now

        settings = get_settings()
        job = JobRepository.enqueue(
            db,
            kind=JobKind.ACTIVATION_APPROVED.value,
            payload={
                "member_id": str(member.id),
                "project_id": str(member.project_id),
                "chat_id": member.telegram_user.telegram_id,
            },
            run_at=now,
            now=now,
            max_attempts=settings.job_max_attempts,
            dedupe_key=f"activation-approved:{member.id}",
        )
        AuditService.record(
            db,
            actor=actor,
            action="member.approved",
            entity_type="project_member",
            entity_id=member.id,
            project_id=member.project_id,
            context={
                "job_id": str(job.id) if job else None,
                "telegram_id": member.telegram_user.telegram_id,
            },
            now=now,
        )
        db.flush()
        return member

    @staticmethod
    def revoke_member(
        db: Session, *, member: ProjectMember, actor: Actor, reason: str = "admin_revoked"
    ) -> ProjectMember:
        now = utcnow()
        if member.status == MemberStatus.REVOKED.value:
            return member
        member.status = MemberStatus.REVOKED.value
        member.revoked_at = now
        member.updated_at = now
        db.execute(
            update(ScheduledJob)
            .where(
                ScheduledJob.status == "pending",
                ScheduledJob.kind == JobKind.ACTIVATION_APPROVED.value,
                ScheduledJob.payload["member_id"].astext == str(member.id),
            )
            .values(status="cancelled", updated_at=now, finished_at=now)
        )
        AuditService.record(
            db,
            actor=actor,
            action="member.revoked",
            entity_type="project_member",
            entity_id=member.id,
            project_id=member.project_id,
            context={"reason": reason},
            now=now,
        )
        db.flush()
        return member

    @staticmethod
    def create_or_get_telegram_user(
        db: Session,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> TelegramUser:
        return TelegramUserRepository.upsert(
            db,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            now=utcnow(),
        )
