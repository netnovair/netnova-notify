from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.domain.enums import LicenseStatus, NotificationStatus, ProjectStatus
from app.models.audit import AuditLog
from app.models.license import License
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.project import Project
from app.models.telegram import ProjectMember
from app.schemas.dashboard import DashboardOut
from app.services.serializers import audit_out


class DashboardService:
    @staticmethod
    def summary(db: Session) -> DashboardOut:
        now = utcnow()
        projects_total = int(db.scalar(select(func.count(Project.id))) or 0)
        projects_active = int(
            db.scalar(
                select(func.count(Project.id)).where(Project.status == ProjectStatus.ACTIVE.value)
            )
            or 0
        )
        notifications_total = int(db.scalar(select(func.count(Notification.id))) or 0)
        queued_notifications = int(
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.status.in_(
                        [
                            NotificationStatus.QUEUED.value,
                            NotificationStatus.SENDING.value,
                            NotificationStatus.RETRY_WAIT.value,
                        ]
                    )
                )
            )
            or 0
        )
        failed_notifications = int(
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.status == NotificationStatus.FAILED.value
                )
            )
            or 0
        )
        open_payments = int(
            db.scalar(select(func.count(Payment.id)).where(Payment.status == "unpaid")) or 0
        )
        rows = db.execute(
            select(Payment.currency, func.coalesce(func.sum(Payment.amount_minor), 0))
            .where(Payment.status == "unpaid")
            .group_by(Payment.currency)
        ).all()
        totals = {row[0]: int(row[1]) for row in rows}
        pending_members = int(
            db.scalar(
                select(func.count(ProjectMember.id)).where(
                    ProjectMember.status == "pending_approval"
                )
            )
            or 0
        )
        soon = now + timedelta(days=14)
        license_attention = int(
            db.scalar(
                select(func.count(License.id)).where(
                    License.status.in_([LicenseStatus.PENDING.value, LicenseStatus.ACTIVE.value]),
                    License.expires_at.is_not(None),
                    License.expires_at <= soon,
                )
            )
            or 0
        )
        recent = list(
            db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(8)).all()
        )
        return DashboardOut(
            projects_total=projects_total,
            projects_active=projects_active,
            notifications_total=notifications_total,
            queued_notifications=queued_notifications,
            failed_notifications=failed_notifications,
            open_payments=open_payments,
            open_payments_amount_by_currency=totals,
            pending_members=pending_members,
            license_attention=license_attention,
            recent_activity=[audit_out(log) for log in recent],
            generated_at=now,
        )
