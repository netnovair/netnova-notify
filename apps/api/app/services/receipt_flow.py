"""Telegram conversation that records a payment receipt.

The employer reaches it from the financial menu (or from the button on a payment
reminder). Steps are intentionally short: amount -> tracking code -> note/image.
``/skip`` is allowed for the optional fields, and everything is re-validated on
the server, so a stale keyboard or a forwarded message cannot post a bogus
amount.

The flow never asks for card numbers: those are shown read-only from
``payment_methods`` and money identifiers never travel in callback data.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.adapters.telegram.base import TelegramAdapter
from app.adapters.telegram.formatting import html_escape, inline_keyboard, truncate
from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import utcnow
from app.domain.attachments import AttachmentInput
from app.domain.payments import format_amount
from app.models.telegram import ProjectMember, TelegramUser
from app.services.accounting import AccountingService, PaymentMethodService, TemplateService
from app.services.orders import fa_digits, normalize_digits

logger = logging.getLogger(__name__)

STEP_AMOUNT = "receipt_amount"
STEP_CODE = "receipt_code"
STEP_NOTE = "receipt_note"
SKIP = "/skip"

MAX_AMOUNT = 10**15
_AMOUNT_JUNK = re.compile(r"[,\u066c\u060c\s]|تومان|ریال|تومن")


def parse_amount(raw: str) -> int | None:
    """Accept «۲۵۰,۰۰۰ تومان» but never a negative or absurd number."""
    text = normalize_digits(raw or "").strip()
    text = _AMOUNT_JUNK.sub("", text)
    if not text.isdigit():
        return None
    value = int(text)
    if not 0 < value <= MAX_AMOUNT:
        return None
    return value


class ReceiptFlow:
    def __init__(
        self,
        db: Session,
        adapter: TelegramAdapter,
        settings: Settings,
        user: TelegramUser,
        chat_id: int,
        member: ProjectMember,
        index: int,
        bot,
    ) -> None:
        self.db = db
        self.adapter = adapter
        self.settings = settings
        self.user = user
        self.chat_id = chat_id
        self.member = member
        self.index = index
        self.bot = bot

    # ------------------------------------------------------------------
    # Presentation
    # ------------------------------------------------------------------
    @property
    def project(self):
        return self.member.project

    def _currency(self) -> str:
        currencies = AccountingService.currencies(self.db, self.member.project_id)
        return currencies[0] if len(currencies) == 1 else "IRT"

    def instructions_text(self) -> str:
        methods = PaymentMethodService.for_project(self.db, self.member.project_id)
        if methods:
            cards = "\n".join(
                f"<b>{html_escape(row.title)}</b>\n"
                f"<code>{row.card_number}</code>\n"
                + (f"{html_escape(row.bank_name)} · " if row.bank_name else "")
                + (html_escape(row.holder_name) if row.holder_name else "")
                + (f"\n{html_escape(row.note)}" if row.note else "")
                for row in methods
            )
        else:
            cards = (
                "شماره کارتی برای واریز ثبت نشده است. برای دریافت اطلاعات واریز با "
                "پشتیبانی تماس بگیرید."
            )
        return TemplateService.render(
            self.db,
            "payment_instructions",
            project_id=self.member.project_id,
            values={
                "project": self.project.name if self.project else "",
                "cards": cards,
                "amount": "",
            },
        )

    def start(self) -> None:
        totals = AccountingService.project_totals(self.db, self.member.project_id)
        total = next((row for row in totals if row.currency == self._currency()), None)
        header = ["<b>ثبت رسید پرداخت</b>", ""]
        if total is not None:
            header.append(
                f"مانده حساب فعلی: <b>{format_amount(total.balance_minor, total.currency)}</b>"
            )
            header.append("")
        self.bot._safe_send(self.chat_id, truncate("\n".join(header) + self.instructions_text()))
        self.bot._set_conversation(
            self.user,
            self.member,
            step=STEP_AMOUNT,
            payload={"index": self.index, "currency": self._currency()},
        )
        self.bot._safe_send(
            self.chat_id,
            "مبلغ واریز شده را به "
            f"{'تومان' if self._currency() == 'IRT' else 'ریال'} بنویسید "
            "(مثلا ۲۵۰۰۰۰۰).",
            inline_keyboard([[("لغو", "cancel")]]),
        )

    def show_history(self) -> None:
        receipts = AccountingService.list_receipts(
            self.db, project_id=self.member.project_id, limit=8
        )
        if not receipts:
            self.bot._safe_send(
                self.chat_id,
                "هنوز رسیدی برای این پروژه ثبت نشده است.",
                inline_keyboard([[("بازگشت", f"{self.index}:fin")]]),
            )
            return
        labels = {
            "pending": "در انتظار بررسی",
            "approved": "تایید شده",
            "rejected": "رد شده",
        }
        lines = ["<b>سوابق رسیدهای شما</b>", ""]
        for receipt in receipts:
            stamp = receipt.created_at.strftime("%Y-%m-%d")
            lines.append(
                f"{stamp} · {format_amount(receipt.amount_minor, receipt.currency)} · "
                f"{labels.get(receipt.status, receipt.status)}"
            )
            if receipt.review_note and receipt.status == "rejected":
                lines.append(f"  دلیل: {html_escape(receipt.review_note[:120])}")
        lines.append("")
        lines.append("<i>تایید نهایی پس از بررسی تیم پشتیبانی انجام می شود.</i>")
        self.bot._safe_send(
            self.chat_id,
            truncate("\n".join(lines)),
            inline_keyboard(
                [
                    [("ارسال رسید جدید", f"{self.index}:rnew")],
                    [("بازگشت", f"{self.index}:fin")],
                ]
            ),
        )

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------
    def _save(self, step: str, payload: dict) -> None:
        self.bot._set_conversation(self.user, self.member, step=step, payload=payload)

    def handle_text(self, conversation, text: str) -> bool:
        payload = dict(conversation.payload or {})
        step = conversation.step
        if step == STEP_AMOUNT:
            amount = parse_amount(text)
            if amount is None:
                self.bot._safe_send(
                    self.chat_id,
                    "مبلغ را فقط با رقم بنویسید (مثلا ۲۵۰۰۰۰۰). برای انصراف /cancel را بزنید.",
                )
                return True
            payload["amount_minor"] = amount
            self._save(STEP_CODE, payload)
            self.bot._safe_send(
                self.chat_id,
                "کد پیگیری واریز یا ۴ رقم آخر کارت را بنویسید. اگر ندارید /skip را بزنید.",
                inline_keyboard([[("لغو", "cancel")]]),
            )
            return True
        if step == STEP_CODE:
            payload["tracking_code"] = None if text.strip() == SKIP else text.strip()[:120]
            self._save(STEP_NOTE, payload)
            self.bot._safe_send(
                self.chat_id,
                "توضیح کوتاه یا تصویر رسید را بفرستید. با /skip می توانید این مرحله را رد کنید.",
                inline_keyboard([[("لغو", "cancel")]]),
            )
            return True
        if step == STEP_NOTE:
            payload["note"] = "" if text.strip() == SKIP else text.strip()[:2000]
            self._submit(payload, attachments=None)
            return True
        return False

    def handle_image(self, conversation, image: tuple[str, str, str], *, caption: str = "") -> bool:
        if conversation.step != STEP_NOTE:
            return False
        attachment = self.bot._download_image(self.chat_id, image)
        if attachment is None:
            return True
        payload = dict(conversation.payload or {})
        # A caption typed with the photo doubles as the receipt note.
        payload["note"] = (caption or payload.get("note") or "").strip()[:2000] or "رسید تصویری"
        self._submit(payload, attachments=[attachment])
        return True

    def _submit(self, payload: dict, *, attachments: list[AttachmentInput] | None) -> None:
        amount = int(payload.get("amount_minor") or 0)
        currency = payload.get("currency") or "IRT"
        try:
            receipt = AccountingService.create_receipt(
                self.db,
                project=self.project,
                actor=_employer_actor(self.member),
                amount_minor=amount,
                currency=currency,
                member_id=self.member.id,
                tracking_code=payload.get("tracking_code"),
                note=payload.get("note") or "",
                attachments=attachments,
                channel="telegram",
                submitted_by_type="employer",
                now=utcnow(),
            )
            self.db.commit()
        except ApiError as exc:
            self.db.rollback()
            self.bot._safe_send(self.chat_id, html_escape(exc.message))
            return
        except Exception:  # noqa: BLE001 - never leak internals into the chat
            self.db.rollback()
            logger.exception("Receipt submission failed")
            self.bot._safe_send(
                self.chat_id, "ثبت رسید انجام نشد. لطفا چند دقیقه بعد دوباره تلاش کنید."
            )
            return
        conversation = self.bot._get_conversation(self.user)
        if conversation is not None:
            self.bot._clear_conversation(conversation)
        text = TemplateService.render(
            self.db,
            "receipt_received",
            project_id=self.member.project_id,
            values={
                "project": self.project.name if self.project else "",
                "amount": format_amount(receipt.amount_minor, receipt.currency),
                "tracking": receipt.tracking_code or "—",
            },
        )
        self.bot._safe_send(
            self.chat_id,
            truncate(text),
            inline_keyboard(
                [
                    [("سوابق واریز", f"{self.index}:rhist")],
                    [("بازگشت به منو", f"{self.index}:home")],
                ]
            ),
        )
        logger.info(
            "Receipt %s submitted by member %s (%s %s)",
            receipt.id,
            self.member.id,
            fa_digits(amount),
            currency,
        )


def _employer_actor(member: ProjectMember):
    from app.services.tickets import actor_for_employer

    return actor_for_employer(member)
