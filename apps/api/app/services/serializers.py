"""Explicit ORM -> API schema mapping (keeps routers thin and consistent)."""

from __future__ import annotations

from datetime import datetime

from app.domain.licenses import effective_status
from app.domain.payments import is_overdue
from app.models.audit import AuditLog
from app.models.catalog import ServiceRequest
from app.models.license import License
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.project import Project
from app.models.telegram import ProjectMember
from app.schemas.audit import AuditLogOut
from app.schemas.catalog import (
    AnswerOut,
    CategoryOut,
    ItemOut,
    QuestionOut,
    RequestListItem,
    RequestOut,
)
from app.schemas.license import LicenseOut
from app.schemas.member import MemberOut
from app.schemas.notification import DeliveryOut, NotificationListItem, NotificationOut
from app.schemas.payment import PaymentOut
from app.schemas.project import FeatureOut, ProjectListItem, ProjectOut, feature_outputs
from app.schemas.ticket import (
    TicketAttachmentOut,
    TicketDetail,
    TicketListItem,
    TicketMessageOut,
)


def member_display_name(member: ProjectMember) -> str:
    user = member.telegram_user
    if user is None:
        return "کاربر تلگرام"
    parts = [part for part in (user.first_name, user.last_name) if part]
    if parts:
        return " ".join(parts)
    if user.username:
        return f"@{user.username}"
    return str(user.telegram_id)


def member_out(member: ProjectMember) -> MemberOut:
    return MemberOut(
        id=member.id,
        telegram_id=member.telegram_user.telegram_id if member.telegram_user else None,
        display_name=member_display_name(member),
        username=member.telegram_user.username if member.telegram_user else None,
        role=member.role,
        status=member.status,
        activated_at=member.activated_at,
        created_at=member.created_at,
        channel_identities=[
            {
                "channel": identity.channel,
                "external_id": identity.external_id,
                "label": identity.label,
            }
            for identity in sorted(member.channel_identities, key=lambda row: row.channel)
        ],
    )


def license_out(license_row: License, now: datetime, project_name: str | None = None) -> LicenseOut:
    return LicenseOut(
        id=license_row.id,
        project_id=license_row.project_id,
        project_name=project_name,
        code_prefix=license_row.code_prefix,
        status=license_row.status,
        expires_at=license_row.expires_at,
        activated_at=license_row.activated_at,
        revoked_at=license_row.revoked_at,
        created_at=license_row.created_at,
        effective_status=effective_status(license_row.status, license_row.expires_at, now),
    )


def _channel_outputs(project: Project) -> list[dict]:
    from app.adapters.messaging.registry import channel_state

    rows = {row.channel: row for row in project.channels}
    result = []
    for state in (channel_state(key) for key in rows):
        # ``channel_state`` uses "label"/"key" internally; expose a stable shape.
        state = {**state, "channel": state["key"]}
        row = rows[state["channel"]]
        result.append(
            {
                "channel": state["channel"],
                "label": state["label"],
                "enabled": row.enabled,
                "configured": state["configured"],
                "mode": state["mode"],
                "beta": state["beta"],
                "recipient_hint": state["recipient_hint"],
                "settings": row.settings or {},
            }
        )
    return result


def project_out(
    project: Project,
    *,
    license_row: License | None,
    open_payments_count: int,
    notifications_count: int,
    now: datetime,
) -> ProjectOut:
    flags = {feature.key: feature.enabled for feature in project.features}
    feature_settings = {feature.key: feature.settings or {} for feature in project.features}
    return ProjectOut(
        id=project.id,
        name=project.name,
        slug=project.slug,
        client_name=project.client_name,
        description=project.description,
        status=project.status,
        is_demo=project.is_demo,
        telegram_connected_at=project.telegram_connected_at,
        archived_at=project.archived_at,
        created_at=project.created_at,
        updated_at=project.updated_at,
        features=feature_outputs(flags, feature_settings),
        channels=_channel_outputs(project),
        license=license_out(license_row, now) if license_row else None,
        members=[member_out(member) for member in project.members],
        open_payments_count=open_payments_count,
        notifications_count=notifications_count,
    )


def project_list_item(
    project: Project,
    *,
    license_row: License | None,
    open_payments_count: int,
    notifications_count: int,
    now: datetime,
    open_tickets: int = 0,
) -> ProjectListItem:
    flags = {feature.key: feature.enabled for feature in project.features}
    employer = next((member for member in project.members if member.status == "active"), None)
    return ProjectListItem(
        id=project.id,
        name=project.name,
        slug=project.slug,
        client_name=project.client_name,
        status=project.status,
        is_demo=project.is_demo,
        archived_at=project.archived_at,
        created_at=project.created_at,
        telegram_connected=employer is not None,
        telegram_connected_at=project.telegram_connected_at,
        employer=member_out(employer) if employer else None,
        license_status=(
            effective_status(license_row.status, license_row.expires_at, now)
            if license_row
            else None
        ),
        license_expires_at=license_row.expires_at if license_row else None,
        enabled_features=[definition for definition, enabled in flags.items() if enabled],
        open_payments_count=open_payments_count,
        notifications_count=notifications_count,
        open_tickets=open_tickets,
    )


def notification_out(notification: Notification) -> NotificationOut:
    return NotificationOut(
        id=notification.id,
        project_id=notification.project_id,
        type=notification.type,
        title=notification.title,
        body=notification.body,
        status=notification.status,
        scheduled_at=notification.scheduled_at,
        queued_at=notification.queued_at,
        sent_at=notification.sent_at,
        cancelled_at=notification.cancelled_at,
        attempt_count=notification.attempt_count,
        last_error=notification.last_error,
        telegram_message_id=notification.telegram_message_id,
        channels=list(notification.channels or ["telegram"]),
        created_at=notification.created_at,
        updated_at=notification.updated_at,
        deliveries=[
            DeliveryOut(
                id=delivery.id,
                channel=delivery.channel or "telegram",
                recipient=delivery.recipient or str(delivery.chat_id or ""),
                chat_id=delivery.chat_id,
                status=delivery.status,
                attempt_no=delivery.attempt_no,
                telegram_message_id=delivery.telegram_message_id,
                error=delivery.error,
                is_mock=delivery.is_mock,
                started_at=delivery.started_at,
                finished_at=delivery.finished_at,
            )
            for delivery in notification.deliveries
        ],
    )


def notification_list_item(
    notification: Notification, project_name: str | None = None, is_mock: bool = False
) -> NotificationListItem:
    return NotificationListItem(
        id=notification.id,
        project_id=notification.project_id,
        project_name=project_name,
        type=notification.type,
        title=notification.title,
        status=notification.status,
        scheduled_at=notification.scheduled_at,
        sent_at=notification.sent_at,
        attempt_count=notification.attempt_count,
        last_error=notification.last_error,
        is_mock=is_mock,
        created_at=notification.created_at,
    )


def payment_out(
    payment: Payment,
    *,
    now: datetime,
    project_name: str | None = None,
    next_reminder_at: datetime | None = None,
) -> PaymentOut:
    return PaymentOut(
        id=payment.id,
        project_id=payment.project_id,
        project_name=project_name,
        title=payment.title,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        due_at=payment.due_at,
        status=payment.status,
        notes=payment.notes,
        paid_at=payment.paid_at,
        cancelled_at=payment.cancelled_at,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
        is_overdue=is_overdue(payment.status, payment.due_at, now),
        next_reminder_at=next_reminder_at,
    )


def audit_out(log: AuditLog) -> AuditLogOut:
    from app.domain.audit_actions import action_label

    return AuditLogOut(
        id=log.id,
        actor_type=log.actor_type,
        actor_label=log.actor_label,
        action=log.action,
        action_label=action_label(log.action),
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        project_id=log.project_id,
        context=log.context or {},
        created_at=log.created_at,
    )


def feature_rows(flags: dict[str, bool]) -> list[FeatureOut]:
    return feature_outputs(flags)


def _ticket_preview(ticket) -> str | None:
    messages = list(ticket.messages or [])
    if not messages:
        return None
    text = " ".join(messages[-1].body.split())
    return text[:120] + ("…" if len(text) > 120 else "")


def ticket_list_item(ticket, now: datetime) -> TicketListItem:
    from datetime import timedelta

    return TicketListItem(
        id=ticket.id,
        project_id=ticket.project_id,
        project_name=ticket.project.name if ticket.project else None,
        subject=ticket.subject,
        status=ticket.status,
        priority=ticket.priority,
        created_by_type=ticket.created_by_type,
        preview=_ticket_preview(ticket),
        message_count=len(ticket.messages or []),
        admin_unread=ticket.admin_unread,
        member_unread=ticket.member_unread,
        last_message_at=ticket.last_message_at,
        is_overdue=(
            ticket.status == "pending_admin" and ticket.last_message_at < now - timedelta(hours=48)
        ),
        created_at=ticket.created_at,
    )


def ticket_detail(ticket, now: datetime) -> TicketDetail:
    base = ticket_list_item(ticket, now)
    member = None
    if ticket.member_id is not None:
        member = next(
            (
                item
                for item in (ticket.project.members if ticket.project else [])
                if item.id == ticket.member_id
            ),
            None,
        )
    return TicketDetail(
        **base.model_dump(),
        messages=[
            TicketMessageOut(
                id=message.id,
                author_type=message.author_type,
                author_label=message.author_label,
                body=message.body,
                channel=message.channel,
                created_at=message.created_at,
                attachments=[
                    TicketAttachmentOut(
                        id=attachment.id,
                        filename=attachment.filename,
                        content_type=attachment.content_type,
                        size_bytes=attachment.size_bytes,
                    )
                    for attachment in message.attachments
                ],
            )
            for message in ticket.messages
        ],
        member_display_name=member_display_name(member) if member else None,
        closed_at=ticket.closed_at,
    )


# ---------------------------------------------------------------------------
# Service catalog and pre-sales orders
# ---------------------------------------------------------------------------
def question_out(question) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        key=question.key,
        label=question.label,
        help_text=question.help_text,
        field_type=question.field_type,
        required=question.required,
        options=[str(option) for option in (question.options or [])],
        min_value=question.min_value,
        max_value=question.max_value,
        order_index=question.order_index,
        is_active=question.is_active,
    )


def item_out(item) -> ItemOut:
    children = sorted(item.children, key=lambda row: row.order_index)
    return ItemOut(
        id=item.id,
        parent_id=item.parent_id,
        level=item.level,
        key=item.key,
        title=item.title,
        description=item.description,
        order_index=item.order_index,
        is_active=item.is_active,
        show_portfolio=item.show_portfolio,
        portfolio_text=item.portfolio_text,
        portfolio_url=item.portfolio_url,
        questions=[question_out(question) for question in item.questions],
        children=[item_out(child) for child in children],
        is_group=bool(children),
    )


def category_out(category) -> CategoryOut:
    items = sorted(category.items, key=lambda row: row.order_index)
    return CategoryOut(
        id=category.id,
        key=category.key,
        title=category.title,
        description=category.description,
        emoji=category.emoji,
        order_index=category.order_index,
        is_active=category.is_active,
        show_portfolio=category.show_portfolio,
        portfolio_text=category.portfolio_text,
        portfolio_url=category.portfolio_url,
        items=[item_out(item) for item in items],
    )


def request_list_item(request: ServiceRequest) -> RequestListItem:
    return RequestListItem(
        id=request.id,
        category_title=request.category_title,
        item_title=request.item_title,
        service_path=request.service_path,
        contact_name=request.contact_name,
        contact_phone=request.contact_phone,
        status=request.status,
        source=request.source,
        telegram_username=request.telegram_username,
        telegram_id=request.telegram_id,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def request_out(request: ServiceRequest) -> RequestOut:
    answers = [
        AnswerOut(
            key=str(item.get("key", "")),
            label=str(item.get("label", "")),
            value=str(item.get("value", "")),
        )
        for item in (request.answers or [])
        if isinstance(item, dict)
    ]
    return RequestOut(
        **request_list_item(request).model_dump(),
        answers=answers,
        admin_note=request.admin_note,
    )
