"""Built-in capabilities.

Each handler receives a ``FeatureContext`` and only talks to the bot service
through its public methods, so a new feature never needs to modify the dispatcher.
"""

from __future__ import annotations

from app.features.base import FeatureContext, FeatureDefinition, register


def _announcements(ctx: FeatureContext) -> None:
    ctx.bot.send_announcements(ctx.chat_id, ctx.member, ctx.index)


def _financial(ctx: FeatureContext) -> None:
    ctx.bot.send_financial(ctx.chat_id, ctx.member, ctx.index)


def _tickets(ctx: FeatureContext) -> None:
    ctx.bot.send_tickets(ctx.chat_id, ctx.member, ctx.index)


def _advisor(ctx: FeatureContext) -> None:
    ctx.bot.send_advisor(ctx.chat_id, ctx.member, ctx.index)


ANNOUNCEMENTS = FeatureDefinition(
    key="announcements",
    label="اطلاعیه های من",
    description="آخرین اطلاعیه های ارسال شده برای این پروژه",
    implemented=True,
    default_enabled=True,
    order=10,
    action="ann",
)

FINANCIAL = FeatureDefinition(
    key="financial",
    label="اطلاعیه های مالی",
    description="وضعیت پرداخت ها و مبالغ باز پروژه",
    implemented=True,
    default_enabled=True,
    order=20,
    action="fin",
)

SUPPORT = FeatureDefinition(
    key="support",
    label="پشتیبانی و تیکت",
    description="ارسال تیکت به تیم نت نووا و مشاهده پاسخ ها",
    implemented=True,
    default_enabled=True,
    order=30,
    action="tickets",
)

ADVISOR = FeatureDefinition(
    key="advisor",
    label="مشاور هوشمند",
    description="پاسخ کوتاه و کاربردی به سوالات آموزشی کارفرما (در حال آماده سازی)",
    implemented=True,
    default_enabled=True,
    order=35,
    action="advice",
)

PERFORMANCE = FeatureDefinition(
    key="performance",
    label="گزارش عملکرد",
    description="در نسخه های بعدی فعال می شود",
    implemented=False,
    default_enabled=True,
    order=40,
    action=None,
)

PROGRESS = FeatureDefinition(
    key="progress",
    label="پیشرفت پروژه",
    description="در نسخه های بعدی فعال می شود",
    implemented=False,
    default_enabled=True,
    order=50,
    action=None,
)


def register_builtin() -> None:
    register(ANNOUNCEMENTS, _announcements)
    register(FINANCIAL, _financial)
    register(SUPPORT, _tickets)
    register(ADVISOR, _advisor)
    register(PERFORMANCE)
    register(PROGRESS)
