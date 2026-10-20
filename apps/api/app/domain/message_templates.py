"""Default Telegram texts and safe placeholder rendering.

Templates are stored in ``message_templates`` and edited from the panel. Rows are
optional: a project without its own row falls back to the global row, and a
missing global row falls back to the defaults below. That keeps a fresh database
working without a data migration, while every text remains editable.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.telegram_html import sanitize_telegram_html


@dataclass(frozen=True)
class TemplateDefinition:
    key: str
    title: str
    description: str
    body: str
    #: Placeholders the editor documents; unknown braces stay untouched.
    variables: tuple[str, ...] = ("project", "name", "amount", "due", "remaining")


PAYMENT_REMINDER = TemplateDefinition(
    key="payment_reminder",
    title="یادآور پرداخت",
    description="پیامی که پیش از سررسید برای کارفرما ارسال می شود.",
    body=(
        "سلام {name} عزیز\n"
        "یادآوری پرداخت برای پروژه <b>{project}</b>\n\n"
        "مبلغ: <b>{amount}</b>\n"
        "سررسید: {due}\n\n"
        "اگر پرداخت را انجام داده اید، از دکمه «ارسال رسید» همین پیام استفاده کنید."
    ),
    variables=("project", "name", "amount", "due", "remaining"),
)

RECEIPT_RECEIVED = TemplateDefinition(
    key="receipt_received",
    title="تایید دریافت رسید",
    description="پاسخ خودکار ربات بعد از ثبت رسید واریز.",
    body=(
        "رسید شما برای پروژه <b>{project}</b> ثبت شد.\n"
        "مبلغ اعلامی: {amount}\n\n"
        "پس از بررسی تیم پشتیبانی، نتیجه به همین گفتگو ارسال می شود."
    ),
    variables=("project", "amount", "tracking"),
)

RECEIPT_APPROVED = TemplateDefinition(
    key="receipt_approved",
    title="تایید پرداخت",
    description="پیامی که بعد از تایید رسید برای کارفرما ارسال می شود.",
    body=(
        "پرداخت شما برای پروژه <b>{project}</b> تایید شد.\n"
        "مبلغ: {amount}\n"
        "مانده حساب: <b>{remaining}</b>"
    ),
    variables=("project", "amount", "remaining", "status"),
)

RECEIPT_REJECTED = TemplateDefinition(
    key="receipt_rejected",
    title="رد رسید",
    description="پیامی که وقتی رسید تایید نمی شود ارسال می شود.",
    body=(
        "رسید ارسالی شما برای پروژه <b>{project}</b> تایید نشد.\n"
        "دلیل: {reason}\n\n"
        "اگر فکر می کنید اشتباهی رخ داده، از بخش «پشتیبانی» تیکت ثبت کنید."
    ),
    variables=("project", "reason"),
)

LICENSE_DELIVERY = TemplateDefinition(
    key="license_delivery",
    title="ارسال لایسنس",
    description="متن همراه با کد لایسنس که به صورت خصوصی برای کارفرما ارسال می شود.",
    body=(
        "سلام {name} عزیز\n"
        "دسترسی شما به پروژه <b>{project}</b> آماده است.\n\n"
        "کد لایسنس:\n<code>{license}</code>\n\n"
        "این کد را در گفتگوی ربات ارسال کنید تا منوی اختصاصی پروژه فعال شود. "
        "کد را در اختیار دیگران قرار ندهید."
    ),
    variables=("project", "name", "license"),
)

PAYMENT_INSTRUCTIONS = TemplateDefinition(
    key="payment_instructions",
    title="راهنمای واریز",
    description="متن آماده‌ای که همراه شماره کارت‌ها در بخش پرداخت ربات نمایش داده می‌شود.",
    body=(
        "برای پرداخت پروژه <b>{project}</b> می‌توانید مبلغ را به یکی از کارت های زیر "
        "واریز کنید و سپس رسید را همین جا ثبت کنید.\n\n"
        "{cards}\n\n"
        "بعد از واریز، دکمه «ارسال رسید» را بزنید و مبلغ، کد پیگیری و تصویر رسید را بفرستید."
    ),
    variables=("project", "cards", "amount"),
)

DEFAULTS: dict[str, TemplateDefinition] = {
    definition.key: definition
    for definition in (
        PAYMENT_REMINDER,
        RECEIPT_RECEIVED,
        RECEIPT_APPROVED,
        RECEIPT_REJECTED,
        LICENSE_DELIVERY,
        PAYMENT_INSTRUCTIONS,
    )
}


def render_template(body: str, values: dict[str, str]) -> str:
    """Substitute ``{placeholders}`` without ever trusting the values.

    Values come from the database (project names, amounts, license codes), so
    they are HTML-escaped before insertion; the template itself is sanitized
    afterwards to keep only Telegram's supported tags.
    """
    from html import escape

    rendered = body
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", escape(str(value), quote=False))
    return sanitize_telegram_html(rendered)
