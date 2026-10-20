"""Shared enums. Stored as strings in the database for migration simplicity."""

from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class FeatureKey(StrEnum):
    """Built-in feature keys.

    The feature registry is not limited to this enum: extensions may register
    additional keys (for example ``invoice``) without a database migration.
    """

    ANNOUNCEMENTS = "announcements"
    FINANCIAL = "financial"
    PERFORMANCE = "performance"
    PROGRESS = "progress"
    SUPPORT = "support"


class ChannelKey(StrEnum):
    TELEGRAM = "telegram"
    BALE = "bale"
    EITAA = "eitaa"
    SMSIR = "smsir"


class TicketStatus(StrEnum):
    OPEN = "open"
    PENDING_ADMIN = "pending_admin"
    PENDING_EMPLOYER = "pending_employer"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TicketAuthorType(StrEnum):
    ADMIN = "admin"
    EMPLOYER = "employer"
    SYSTEM = "system"


class LicenseStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class MemberStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    REVOKED = "revoked"


class MemberRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class NotificationType(StrEnum):
    ANNOUNCEMENT = "announcement"
    FINANCIAL = "financial"
    SYSTEM = "system"


class NotificationStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    RETRY_WAIT = "retry_wait"
    CANCELLED = "cancelled"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    UNKNOWN = "unknown"


class PaymentStatus(StrEnum):
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class ReceiptStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Currency(StrEnum):
    IRR = "IRR"
    IRT = "IRT"
    USD = "USD"
    EUR = "EUR"


class JobKind(StrEnum):
    NOTIFICATION_SEND = "notification_send"
    PAYMENT_REMINDER = "payment_reminder"
    ACTIVATION_APPROVED = "activation_approved"
    TICKET_NOTIFY = "ticket_notify"
    RECEIPT_SUBMITTED = "receipt_submitted"
    RECEIPT_RESULT = "receipt_result"
    LICENSE_DELIVERY = "license_delivery"


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActorType(StrEnum):
    ADMIN = "admin"
    TELEGRAM_USER = "telegram_user"
    SYSTEM = "system"


TERMINAL_NOTIFICATION_STATUSES = {
    NotificationStatus.SENT,
    NotificationStatus.FAILED,
    NotificationStatus.CANCELLED,
}
