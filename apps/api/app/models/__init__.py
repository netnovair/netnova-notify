"""Import every model so SQLAlchemy metadata and Alembic see the full schema."""

from app.models.accounting import (
    MessageTemplate,
    PaymentAllocation,
    PaymentMethod,
    PaymentReceipt,
    PaymentReceiptFile,
)
from app.models.admin import AdminSession, AdminUser
from app.models.audit import AuditLog
from app.models.catalog import (
    OrderSession,
    ServiceCategory,
    ServiceItem,
    ServiceQuestion,
    ServiceRequest,
)
from app.models.job import ScheduledJob
from app.models.license import License
from app.models.notification import DeliveryAttempt, Notification
from app.models.payment import Payment
from app.models.project import Project, ProjectChannel, ProjectFeature
from app.models.system import SystemState
from app.models.telegram import ProjectMember, TelegramUpdate, TelegramUser
from app.models.ticket import (
    MemberChannelIdentity,
    TelegramConversation,
    Ticket,
    TicketMessage,
)

__all__ = [
    "AdminSession",
    "MessageTemplate",
    "PaymentAllocation",
    "PaymentMethod",
    "PaymentReceipt",
    "PaymentReceiptFile",
    "AdminUser",
    "AuditLog",
    "ScheduledJob",
    "OrderSession",
    "ServiceCategory",
    "ServiceItem",
    "ServiceQuestion",
    "ServiceRequest",
    "License",
    "DeliveryAttempt",
    "Notification",
    "Payment",
    "MemberChannelIdentity",
    "Project",
    "ProjectChannel",
    "ProjectFeature",
    "TelegramConversation",
    "Ticket",
    "TicketMessage",
    "ProjectMember",
    "TelegramUpdate",
    "SystemState",
    "TelegramUser",
]
