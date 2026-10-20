"""Telegram update handling for the central employer bot.

Security rules implemented here:
* only private chats are processed;
* callback data never contains database ids, license codes or financial data,
  only short action codes that are re-validated against fresh database access;
* every menu action re-checks project status, license validity and membership;
* feature capabilities come from the registry, so unimplemented features answer
  with an explicit "coming soon" message and never fabricated data.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.telegram.base import TelegramAdapter, TelegramError
from app.adapters.telegram.formatting import (
    html_escape,
    inline_keyboard,
    reply_keyboard,
)
from app.core.config import Settings
from app.core.errors import ApiError
from app.core.rate_limit import rate_limiter
from app.core.security import normalize_license_code, utcnow
from app.domain.attachments import (
    ALLOWED_IMAGE_TYPES,
    MAX_ATTACHMENT_BYTES,
    AttachmentInput,
)
from app.domain.features import enabled_features
from app.domain.jalali import format_jalali_date
from app.domain.menu import (
    project_menu_buttons,
    project_picker_buttons,
    soon_key_for_callback,
)
from app.domain.payments import format_amount, is_overdue
from app.domain.telegram_html import sanitize_telegram_html, truncate_html
from app.features import FeatureContext, find_by_action, get_feature, handler_for
from app.models.payment import Payment
from app.models.system import SystemState
from app.models.telegram import ProjectMember, TelegramUser
from app.repositories.licenses import MemberRepository
from app.repositories.notifications import NotificationRepository
from app.repositories.users import TelegramUserRepository
from app.services.accounting import AccountingService
from app.services.catalog import CatalogService
from app.services.licenses import LicenseService
from app.services.order_flow import (
    HELP_BUTTON,
    MENU_BUTTON,
    ORDER_BUTTON,
    OrderFlow,
)
from app.services.tickets import TicketService, actor_for_employer

logger = logging.getLogger(__name__)

WELCOME = (
    "به ربات <b>نت نووا</b> خوش آمدید.\n\n"
    "از اینجا می توانید اطلاعیه ها و وضعیت پروژه های خود را ببینید یا برای "
    "خدمات گرافیک، سایت، اپلیکیشن، تولید محتوا و سئو سفارش ثبت کنید.\n\n"
    "برای ثبت سفارش روی دکمه «ثبت سفارش» بزنید تا در چند سوال کوتاه، نیاز شما را "
    "دقیق تر بشناسیم.\n"
    "اگر کد لایسنس پروژه را دارید، آن را به صورت یک پیام ارسال کنید.\n"
    "نمونه کد: <code>NN-XXXX-XXXX-XXXX-XXXX</code>"
)

HELP = (
    "<b>راهنما</b>\n\n"
    "دستورها:\n"
    "/start شروع و نمایش منو\n"
    "/menu نمایش منوی پروژه\n"
    "/cancel لغو سفارش یا عملیات جاری\n"
    "/help همین راهنما\n\n"
    "برای ثبت سفارش از دکمه «ثبت سفارش» استفاده کنید؛ فقط نام، شماره تماس و "
    "چند سوال کوتاه درباره نیاز شما پرسیده می شود.\n"
    "برای اتصال پروژه، کد لایسنس را به صورت یک پیام ارسال کنید.\n"
    "برای دیدن اطلاعیه ها و وضعیت مالی از دکمه های منو استفاده کنید."
)

SOON_TEMPLATE = "قابلیت «{label}» به زودی فعال می شود."

#: Registered with Telegram so the command list is visible in the client.
BOT_COMMANDS = [
    {"command": "start", "description": "شروع و نمایش منو"},
    {"command": "menu", "description": "منوی پروژه ها"},
    {"command": "cancel", "description": "لغو سفارش یا عملیات جاری"},
    {"command": "help", "description": "راهنما"},
]

STEP_ADVISOR = "advisor_question"
CONVERSATION_TTL_MINUTES = 30


class TelegramBotService:
    def __init__(self, db: Session, adapter: TelegramAdapter, settings: Settings) -> None:
        self.db = db
        self.adapter = adapter
        self.settings = settings

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def handle_update(self, update: dict) -> None:
        self._record_update(update)
        if update.get("callback_query"):
            self._handle_callback(update["callback_query"])
            return
        message = update.get("message")
        if not message:
            return
        chat = message.get("chat") or {}
        if chat.get("type") != "private":
            return
        sender = message.get("from") or {}
        if not sender.get("id") or sender.get("is_bot"):
            return
        chat_id = int(chat["id"])
        user = self._upsert_user(sender)
        text = (message.get("text") or message.get("caption") or "").strip()
        image = self._extract_image(message)
        if image is not None and not text.startswith("/"):
            self._handle_image_message(user, chat_id, image, caption=text)
            return
        if not text:
            return

        # Persistent reply-keyboard buttons arrive as ordinary text messages.
        if text == ORDER_BUTTON:
            self._start_order(user, chat_id)
            return
        if text == MENU_BUTTON:
            self._cancel_flows(user)
            self._ensure_menu_keyboard(user, chat_id)
            self._send_home(user, chat_id)
            return
        if text == HELP_BUTTON:
            self._send_help(chat_id)
            return

        if text.startswith("/start"):
            self._cancel_flows(user)
            self._ensure_menu_keyboard(user, chat_id)
            self._send_home(user, chat_id)
            return
        if text.startswith("/menu"):
            self._ensure_menu_keyboard(user, chat_id)
            self._send_home(user, chat_id)
            return
        if text.startswith("/help"):
            self._send_help(chat_id)
            return
        if text.startswith("/cancel"):
            self._cancel_command(user, chat_id)
            return

        if self._looks_like_license(text):
            self._cancel_flows(user)
            self._handle_license_submission(user, chat_id, text)
            return
        if self._order_flow(user, chat_id).handle_text(text):
            return
        if self._handle_conversation(user, chat_id, text):
            return
        self._safe_send(
            chat_id,
            "برای ثبت سفارش از دکمه «ثبت سفارش» استفاده کنید، "
            "یا برای اتصال پروژه کد لایسنس را ارسال کنید.\n"
            "برای مشاهده منو /start را بزنید.",
            inline_keyboard([[("ثبت سفارش", "o:home"), ("راهنما", "help")]]),
        )

    @staticmethod
    def _extract_image(message: dict) -> tuple[str, str, str] | None:
        """Return ``(file_id, filename, content_type)`` for a sent image.

        Telegram delivers ordinary photos in several sizes (ascending); the last
        one is the largest. Images sent "as file" arrive as a document and are
        accepted only when the declared MIME type is a safe raster format.
        """
        photos = message.get("photo")
        if isinstance(photos, list) and photos:
            file_id = (photos[-1] or {}).get("file_id")
            if file_id:
                return str(file_id), "telegram-photo.jpg", "image/jpeg"
        document = message.get("document") or {}
        mime = str(document.get("mime_type") or "")
        file_id = document.get("file_id")
        if file_id and mime in ALLOWED_IMAGE_TYPES:
            return str(file_id), str(document.get("file_name") or "telegram-file"), mime
        return None

    def _handle_image_message(
        self,
        user: TelegramUser,
        chat_id: int,
        image: tuple[str, str, str],
        *,
        caption: str = "",
    ) -> None:
        """Images only make sense inside an open ticket conversation."""
        if not self._handle_conversation(user, chat_id, caption, image=image):
            self._safe_send(
                chat_id,
                "برای ارسال تصویر، ابتدا از منوی «تیکت ها» یک تیکت باز کنید یا پاسخ "
                "همان تیکت را بزنید، یا در بخش «وضعیت مالی» گزینه «ارسال رسید» را انتخاب "
                "کنید؛ سپس تصویر را همراه متن یا به تنهایی بفرستید.",
                inline_keyboard([[("منوی اصلی", "h")]]),
            )

    def _download_image(self, chat_id: int, image: tuple[str, str, str]) -> AttachmentInput | None:
        file_id, filename, content_type = image
        try:
            data = self.adapter.download_file(file_id, MAX_ATTACHMENT_BYTES)
        except TelegramError:
            logger.warning("Telegram image download failed for file %s", file_id)
            self._safe_send(chat_id, "دریافت تصویر از تلگرام ممکن نشد. لطفا دوباره ارسال کنید.")
            return None
        except Exception:  # noqa: BLE001 - never expose internals in chat
            logger.exception("Unexpected image download failure")
            self._safe_send(chat_id, "دریافت تصویر از تلگرام ممکن نشد. لطفا دوباره ارسال کنید.")
            return None
        return AttachmentInput(data=data, filename=filename, content_type=content_type)

    # ------------------------------------------------------------------
    # Messages / activation
    # ------------------------------------------------------------------
    def _handle_license_submission(self, user: TelegramUser, chat_id: int, text: str) -> None:
        limit_key = f"activation:{user.telegram_id}"
        if not rate_limiter.allow(limit_key, self.settings.activation_rate_limit, 60):
            self._safe_send(
                chat_id,
                "تعداد تلاش های شما برای فعال سازی بیش از حد مجاز است. یک دقیقه بعد دوباره تلاش کنید.",
            )
            return
        try:
            result = LicenseService.activate(self.db, code=text, telegram_user=user)
        except ApiError as exc:
            self._safe_send(chat_id, html_escape(exc.message))
            return
        except Exception:  # noqa: BLE001 - never expose internals in chat
            logger.exception("License activation failed")
            self._safe_send(chat_id, "خطایی در فعال سازی رخ داد. لطفا بعدا دوباره تلاش کنید.")
            return

        if result.already_active:
            note = "اتصال شما از قبل فعال بود."
            self._send_home(user, chat_id, note=note)
            return

        self._safe_send(
            chat_id,
            f"درخواست اتصال شما به پروژه <b>{html_escape(result.project_name)}</b> ثبت شد.\n\n"
            "پس از تایید مدیر، منوی اطلاعیه ها برای شما فعال می شود.",
        )
        self._notify_admin_of_request(user, result.project_name)

    def _notify_admin_of_request(self, user: TelegramUser, project_name: str) -> None:
        if not self.settings.admin_telegram_chat_id:
            return
        display = " ".join(part for part in (user.first_name, user.last_name) if part) or str(
            user.telegram_id
        )
        text = (
            "<b>درخواست اتصال کارفرما</b>\n"
            f"پروژه: {html_escape(project_name)}\n"
            f"کارفرما: {html_escape(display)}\n"
            f"نام کاربری: @{html_escape(user.username or '-')}\n"
            f"شناسه تلگرام: <code>{user.telegram_id}</code>\n\n"
            "برای تایید یا رد درخواست به پنل مدیریت مراجعه کنید."
        )
        try:
            self.adapter.send_message(self.settings.admin_telegram_chat_id, text)
        except TelegramError:
            logger.warning("Could not notify admin about a new activation request.")

    @staticmethod
    def _looks_like_license(text: str) -> bool:
        normalized = normalize_license_code(text)
        return normalized.startswith("NN") and len(normalized) >= 16

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _handle_callback(self, callback: dict) -> None:
        callback_id = callback.get("id")
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        sender = callback.get("from") or {}
        if not sender.get("id") or chat.get("type") != "private":
            return
        chat_id = int(chat["id"])
        user = self._upsert_user(sender)
        data = (callback.get("data") or "").strip()
        memberships = LicenseService.access_memberships(self.db, user)

        try:
            handled = self._dispatch_callback(chat_id, user, memberships, data)
        except Exception:  # noqa: BLE001
            logger.exception("Telegram callback handling failed")
            handled = False
        if not handled:
            self.adapter.answer_callback(callback_id, "درخواست معتبر نیست.")
        else:
            self.adapter.answer_callback(callback_id)

    def _dispatch_callback(
        self,
        chat_id: int,
        user: TelegramUser,
        memberships: list[ProjectMember],
        data: str,
    ) -> bool:
        if data == "cancel":
            conversation = self._get_conversation(user)
            if conversation is not None:
                self._clear_conversation(conversation)
            self._safe_send(
                chat_id,
                "عملیات لغو شد. هر زمان خواستید از منو دوباره شروع کنید.",
                inline_keyboard([[("منوی اصلی", "h")]]),
            )
            return True
        if data == "h":
            self._send_home(user, chat_id)
            return True
        if data == "help":
            self._send_help(chat_id)
            return True
        if data == "pf":
            self._send_portfolio(chat_id)
            return True
        if data.startswith(
            (
                "o:",
                "oc:",
                "oi:",
                "op:",
                "opf:",
                "oq:",
                "oback",
                "oup",
                "oskip",
                "osubmit",
                "ox",
            )
        ):
            return self._order_flow(user, chat_id).handle_callback(data)
        if data.startswith("p:") and data[2:].isdigit():
            index = int(data[2:])
            if 0 <= index < len(memberships):
                self._send_project_menu(chat_id, memberships[index], index)
                return True
            return False

        parts = data.split(":")
        if not parts or not parts[0].isdigit():
            return False
        index = int(parts[0])
        if not (0 <= index < len(memberships)):
            self._safe_send(chat_id, "دسترسی شما به این پروژه فعال نیست. لطفا /start را بزنید.")
            return True
        member = memberships[index]

        if len(parts) == 2 and parts[1] == "cancel":
            conversation = self._get_conversation(user)
            if conversation is not None:
                self._clear_conversation(conversation)
            self._safe_send(
                chat_id,
                "عملیات لغو شد.",
                inline_keyboard(
                    [[("وضعیت مالی", f"{index}:fin")], [("منوی اصلی", f"{index}:home")]]
                ),
            )
            return True
        if len(parts) == 2 and parts[1] == "home":
            self._send_home(user, chat_id)
            return True
        if len(parts) == 2 and parts[1] == "rnew":
            from app.services.receipt_flow import ReceiptFlow

            ReceiptFlow(
                self.db, self.adapter, self.settings, user, chat_id, member, index, self
            ).start()
            return True
        if len(parts) == 2 and parts[1] == "rhist":
            from app.services.receipt_flow import ReceiptFlow

            ReceiptFlow(
                self.db, self.adapter, self.settings, user, chat_id, member, index, self
            ).show_history()
            return True
        if len(parts) == 2 and parts[1] == "rinv":
            self._send_invoices(chat_id, member, index)
            return True
        if len(parts) == 2 and parts[1] == "rcards":
            self._send_cards(chat_id, user, member, index)
            return True
        if len(parts) == 2 and parts[1] == "newticket":
            self._start_ticket_flow(user, member, chat_id)
            return True
        if len(parts) == 3 and parts[1] == "ticket" and parts[2].isdigit():
            self._show_ticket(chat_id, member, index, int(parts[2]))
            return True
        if len(parts) == 3 and parts[1] == "treply" and parts[2].isdigit():
            self._start_ticket_reply(user, member, chat_id, int(parts[2]))
            return True
        if len(parts) == 3 and parts[1] == "soon":
            key = soon_key_for_callback(data)
            if key is None:
                return False
            definition = get_feature(key)
            if definition is None or definition.implemented:
                return False
            text = SOON_TEMPLATE.format(label=definition.label)
            self._safe_send(
                chat_id,
                text,
                inline_keyboard([[("بازگشت به منو", f"{index}:home")]]),
            )
            return True
        if len(parts) == 2:
            registered = find_by_action(parts[1])
            if registered is None:
                return False
            handler = handler_for(registered.definition.key)
            if handler is None:
                # Declared but not implemented: answer explicitly, never fake data.
                text = SOON_TEMPLATE.format(label=registered.definition.label)
                self._safe_send(
                    chat_id,
                    text,
                    inline_keyboard([[("بازگشت به منو", f"{index}:home")]]),
                )
                return True
            handler(
                FeatureContext(
                    db=self.db,
                    adapter=self.adapter,
                    settings=self.settings,
                    chat_id=chat_id,
                    member=member,
                    index=index,
                    bot=self,
                )
            )
            return True
        return False

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------
    def _send_home(self, user: TelegramUser, chat_id: int, note: str | None = None) -> None:
        memberships = LicenseService.access_memberships(self.db, user)
        if memberships:
            if len(memberships) == 1:
                self._send_project_menu(chat_id, memberships[0], 0, note=note)
            else:
                prefix = f"{html_escape(note)}\n\n" if note else ""
                text = (
                    f"{prefix}<b>پروژه های شما</b>\nبرای مشاهده منوی هر پروژه، آن را انتخاب کنید."
                )
                buttons = project_picker_buttons(
                    [(member.project.name, index) for index, member in enumerate(memberships)]
                )
                self._safe_send(chat_id, text, buttons)
            return

        pending = [
            member
            for member in MemberRepository.memberships_for_user(self.db, user.id)
            if member.status == "pending_approval"
        ]
        if pending:
            names = "، ".join(html_escape(member.project.name) for member in pending)
            self._safe_send(
                chat_id,
                f"درخواست اتصال شما به پروژه <b>{names}</b> ثبت شده و در انتظار تایید مدیر است.\n\n"
                "تا آن زمان می توانید از دکمه «ثبت سفارش» برای سفارش خدمات جدید استفاده کنید.",
                inline_keyboard([[("ثبت سفارش", "o:home"), ("نمونه کارها", "pf")]]),
            )
            return

        self._safe_send(
            chat_id,
            WELCOME,
            inline_keyboard(
                [
                    [("ثبت سفارش", "o:home")],
                    [("نمونه کارها", "pf"), ("راهنما", "help")],
                ]
            ),
        )

    def _send_project_menu(
        self,
        chat_id: int,
        member: ProjectMember,
        index: int,
        note: str | None = None,
    ) -> None:
        project = member.project
        flags = {feature.key: feature.enabled for feature in project.features}
        expiry = (
            format_jalali_date(member.license.expires_at, self.settings.tehran_timezone)
            if member.license and member.license.expires_at
            else "بدون تاریخ انقضا"
        )
        prefix = f"{html_escape(note)}\n\n" if note else ""
        text = (
            f"{prefix}<b>{html_escape(project.name)}</b>\n"
            f"<i>{html_escape(project.client_name)}</i>\n\n"
            "وضعیت اتصال: فعال\n"
            f"اعتبار لایسنس تا: {expiry}\n\n"
            "برای دریافت اطلاعات، یکی از گزینه های زیر را انتخاب کنید."
        )
        enabled = enabled_features(flags)
        if not enabled:
            text += "\n\nدر حال حاضر قابلیتی برای این پروژه فعال نشده است."
        self._safe_send(chat_id, truncate_html(text), project_menu_buttons(index, flags))

    def send_announcements(self, chat_id: int, member: ProjectMember, index: int) -> None:
        self._send_announcements(chat_id, member, index)

    def _send_announcements(self, chat_id: int, member: ProjectMember, index: int) -> None:
        notifications = NotificationRepository.recent_sent(self.db, member.project_id, limit=5)
        if not notifications:
            self._safe_send(
                chat_id,
                f"برای پروژه <b>{html_escape(member.project.name)}</b> هنوز اطلاعیه ای ارسال نشده است.",
                inline_keyboard([[("بازگشت به منو", f"{index}:home")]]),
            )
            return
        parts = [f"<b>اطلاعیه های {html_escape(member.project.name)}</b>"]
        for notification in notifications:
            sent_at = notification.sent_at or notification.created_at
            parts.append(
                f"<b>{html_escape(notification.title)}</b>\n"
                f"<i>{format_jalali_date(sent_at, self.settings.tehran_timezone)}</i>\n"
                # Announcement bodies may carry Telegram markup; escaping would
                # show the tags literally, so they are sanitized instead.
                f"{sanitize_telegram_html(notification.body)}"
            )
        self._safe_send(
            chat_id,
            truncate_html("\n\n".join(parts)),
            inline_keyboard([[("بازگشت به منو", f"{index}:home")]]),
        )

    def send_financial(self, chat_id: int, member: ProjectMember, index: int) -> None:
        self._send_financial(chat_id, member, index)

    # ------------------------------------------------------------------
    # AI advisor (structure only until an API key exists)
    # ------------------------------------------------------------------
    def send_advisor(self, chat_id: int, member: ProjectMember, index: int) -> None:
        from app.services.advisor import AdvisorService

        back = inline_keyboard([[("بازگشت به منو", f"{index}:home")]])
        status = AdvisorService.status(self.settings)
        if not status.available:
            # Never improvise an answer when the provider is not configured.
            self._safe_send(
                chat_id,
                "قابلیت «مشاور هوشمند» به زودی فعال می شود.\n"
                "تا آن زمان می توانید سوال خود را از بخش «پشتیبانی و تیکت» بپرسید.",
                back,
            )
            return
        if member.telegram_user is None:
            self._safe_send(chat_id, "برای استفاده از مشاور، حساب تلگرام شما باید متصل باشد.", back)
            return
        self._set_conversation(
            member.telegram_user,
            member,
            step=STEP_ADVISOR,
            payload={"index": index},
        )
        self._safe_send(
            chat_id,
            "سوال خود را کوتاه بنویسید؛ پاسخ حداکثر ۶ خط خواهد بود.\n"
            "برای انصراف /cancel را بفرستید.",
            inline_keyboard([[("لغو", "cancel")]]),
        )

    def _send_financial(self, chat_id: int, member: ProjectMember, index: int) -> None:
        invoices_exist = bool(AccountingService.invoices(self.db, member.project_id))
        totals = (
            AccountingService.project_totals(self.db, member.project_id) if invoices_exist else []
        )
        project_name = html_escape(member.project.name)
        rows: list[list[tuple[str, str]]] = [
            [("ارسال رسید", f"{index}:rnew")],
            [("سوابق واریز", f"{index}:rhist"), ("فاکتورها", f"{index}:rinv")],
            [("شماره کارت ها", f"{index}:rcards")],
            [("بازگشت به منو", f"{index}:home")],
        ]
        if not invoices_exist:
            self._safe_send(
                chat_id,
                f"برای پروژه <b>{project_name}</b> هنوز فاکتوری ثبت نشده است.\n"
                "اگر مبلغی واریز کرده اید، از دکمه «ارسال رسید» استفاده کنید.",
                inline_keyboard(rows),
            )
            return
        lines = [f"<b>وضعیت مالی {project_name}</b>", ""]
        for total in totals:
            lines.append(f"بدهی: <b>{format_amount(total.debt_minor, total.currency)}</b>")
            if total.overdue_minor:
                lines.append(f"سررسید گذشته: {format_amount(total.overdue_minor, total.currency)}")
            lines.append(f"پرداخت شده: {format_amount(total.paid_minor, total.currency)}")
            if total.credit_minor:
                lines.append(f"اعتبار: {format_amount(total.credit_minor, total.currency)}")
            lines.append(
                "مانده حساب: "
                + (
                    "<b>تسویه</b>"
                    if total.settled
                    else f"<b>{format_amount(total.balance_minor, total.currency)}</b>"
                )
            )
            lines.append("")
        pending = AccountingService.pending_receipts(self.db, member.project_id)
        if pending:
            lines.append(f"<i>{pending} رسید در انتظار بررسی دارید.</i>")
            lines.append("")
        lines.append(
            "<i>این اعداد از فاکتورها و رسیدهای تاییدشده محاسبه می شوند؛ "
            "تایید تراکنش بانکی با پشتیبانی است.</i>"
        )
        self._safe_send(chat_id, truncate_html("\n".join(lines)), inline_keyboard(rows))

    def _send_invoices(self, chat_id: int, member: ProjectMember, index: int) -> None:
        invoices = AccountingService.invoices(self.db, member.project_id)
        back = inline_keyboard([[("ارسال رسید", f"{index}:rnew")], [("بازگشت", f"{index}:fin")]])
        if not invoices:
            self._safe_send(chat_id, "فاکتوری برای این پروژه ثبت نشده است.", back)
            return
        now = utcnow()
        lines = ["<b>فاکتورهای پروژه</b>", ""]
        for payment in invoices:
            lines.append(self._format_payment(payment, now))
        self._safe_send(chat_id, truncate_html("\n\n".join(lines)), back)

    def _send_cards(
        self, chat_id: int, user: TelegramUser, member: ProjectMember, index: int
    ) -> None:
        from app.services.receipt_flow import ReceiptFlow

        flow = ReceiptFlow(self.db, self.adapter, self.settings, user, chat_id, member, index, self)
        self._safe_send(
            chat_id,
            truncate_html(flow.instructions_text()),
            inline_keyboard(
                [
                    [("ارسال رسید", f"{index}:rnew")],
                    [("بازگشت", f"{index}:fin")],
                ]
            ),
        )

    def _format_payment(self, payment: Payment, now: datetime) -> str:
        overdue = is_overdue(payment.status, payment.due_at, now)
        due = format_jalali_date(payment.due_at, self.settings.tehran_timezone)
        status = {
            "unpaid": "پرداخت نشده",
            "partially_paid": "پرداخت جزئی",
            "paid": "تسویه شده",
            "cancelled": "لغو شده",
        }.get(payment.status, payment.status)
        if overdue:
            status = "سررسید شده"
        remaining = max(0, payment.amount_minor - payment.amount_paid_minor)
        lines = [
            f"<b>{html_escape(payment.title)}</b>",
            f"مبلغ: {format_amount(payment.amount_minor, payment.currency)}",
        ]
        if payment.amount_paid_minor:
            lines.append(
                f"پرداخت شده: {format_amount(payment.amount_paid_minor, payment.currency)}"
            )
        if remaining:
            lines.append(f"مانده: {format_amount(remaining, payment.currency)}")
        lines.extend([f"سررسید: {due}", f"وضعیت: {status}"])
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tickets (two-way support)
    # ------------------------------------------------------------------
    def send_tickets(self, chat_id: int, member: ProjectMember, index: int) -> None:
        tickets = TicketService.employer_tickets(
            self.db, project_id=member.project_id, member_id=member.id
        )
        rows: list[list[tuple[str, str]]] = []
        if tickets:
            parts = [f"<b>تیکت های {html_escape(member.project.name)}</b>", ""]
            for position, ticket in enumerate(tickets, start=1):
                last = ticket.messages[-1] if ticket.messages else None
                status = {
                    "open": "باز",
                    "pending_admin": "در انتظار پاسخ پشتیبانی",
                    "pending_employer": "پاسخ داده شده",
                    "closed": "بسته شده",
                }.get(ticket.status, ticket.status)
                parts.append(
                    f"{position}. <b>{html_escape(ticket.subject)}</b>\n"
                    f"وضعیت: {status}\n"
                    f"آخرین پیام: {html_escape((last.body if last else '')[:120])}"
                )
                rows.append([(f"مشاهده تیکت {position}", f"{index}:ticket:{position - 1}")])
            text = truncate_html("\n\n".join(parts))
        else:
            text = "هنوز تیکتی برای این پروژه ثبت نکرده اید."
        rows.append([("ثبت تیکت جدید", f"{index}:newticket")])
        rows.append([("بازگشت به منو", f"{index}:home")])
        self._safe_send(chat_id, text, inline_keyboard(rows))

    def _ticket_at(self, member: ProjectMember, ordinal: int):
        """Resolve an ordinal from a callback to the employer's own ticket list.

        Callback data never contains database ids. The ordinal is re-resolved for
        this member only, so it cannot address another employer's ticket.
        """
        tickets = TicketService.employer_tickets(
            self.db, project_id=member.project_id, member_id=member.id, limit=20
        )
        if 0 <= ordinal < len(tickets):
            return tickets[ordinal]
        return None

    def _show_ticket(self, chat_id: int, member: ProjectMember, index: int, ordinal: int) -> None:
        ticket = self._ticket_at(member, ordinal)
        back = inline_keyboard([[("بازگشت به فهرست", f"{index}:tickets")]])
        if ticket is None:
            self._safe_send(chat_id, "این تیکت یافت نشد.", back)
            return
        lines = [
            f"<b>{html_escape(ticket.subject)}</b>",
            "",
        ]
        for message in ticket.messages[-6:]:
            admin_message = message.author_type == "admin"
            who = "پشتیبانی" if admin_message else "شما"
            body = (
                sanitize_telegram_html(message.body) if admin_message else html_escape(message.body)
            )
            lines.append(
                f"<b>{who}</b> - <i>{format_jalali_date(message.created_at, self.settings.tehran_timezone)}</i>\n"
                f"{body}"
            )
        if ticket.status == "closed":
            lines.append("")
            lines.append("<i>این تیکت بسته شده است؛ ارسال پاسخ آن را دوباره باز می کند.</i>")
        rows = [
            [("پاسخ به این تیکت", f"{index}:treply:{ordinal}")],
            [("بازگشت به فهرست", f"{index}:tickets")],
        ]
        self._safe_send(chat_id, truncate_html("\n\n".join(lines)), inline_keyboard(rows))

    def _start_ticket_reply(
        self, user: TelegramUser, member: ProjectMember, chat_id: int, ordinal: int
    ) -> None:
        ticket = self._ticket_at(member, ordinal)
        if ticket is None:
            self._safe_send(chat_id, "این تیکت یافت نشد.")
            return
        self._set_conversation(
            user,
            member,
            step="ticket_reply",
            payload={"ticket_id": str(ticket.id), "subject": ticket.subject},
        )
        self._safe_send(
            chat_id,
            f"پاسخ خود را برای تیکت «{html_escape(ticket.subject)}» بنویسید. یا /cancel را بفرستید.",
            inline_keyboard([[("لغو", f"{self._index_of(member)}:home")]]),
        )

    def _start_ticket_flow(self, user: TelegramUser, member: ProjectMember, chat_id: int) -> None:
        # One active flow per user keeps text messages unambiguous.
        self._order_flow(user, chat_id).cancel()
        self._set_conversation(user, member, step="ticket_subject", payload={})
        self._safe_send(
            chat_id,
            "موضوع تیکت را در یک پیام کوتاه بنویسید. برای لغو، /cancel را ارسال کنید.",
            inline_keyboard([[("لغو", f"{self._index_of(member)}:home")]]),
        )

    def _handle_conversation(
        self,
        user: TelegramUser,
        chat_id: int,
        text: str,
        *,
        image: tuple[str, str, str] | None = None,
    ) -> bool:
        conversation = self._get_conversation(user)
        if conversation is None:
            return False
        from app.services.receipt_flow import STEP_AMOUNT, STEP_CODE, STEP_NOTE, ReceiptFlow

        receipt_steps = (STEP_AMOUNT, STEP_CODE, STEP_NOTE)
        if conversation.step in receipt_steps:
            member = next(
                (
                    item
                    for item in LicenseService.access_memberships(self.db, user)
                    if str(item.id) == str(conversation.payload.get("member_id"))
                ),
                None,
            )
            if member is None:
                self._clear_conversation(conversation)
                self._safe_send(chat_id, "دسترسی شما به این پروژه فعال نیست. لطفا /start را بزنید.")
                return True
            if text.startswith("/cancel"):
                self._clear_conversation(conversation)
                self._safe_send(
                    chat_id,
                    "ثبت رسید لغو شد. هر وقت خواستید از بخش «وضعیت مالی» دوباره شروع کنید.",
                    inline_keyboard([[("منوی اصلی", f"{self._index_of(member)}:home")]]),
                )
                return True
            if text.startswith("/") and text.strip() != "/skip":
                self._clear_conversation(conversation)
                return False
            flow = ReceiptFlow(
                self.db,
                self.adapter,
                self.settings,
                user,
                chat_id,
                member,
                int(conversation.payload.get("index") or self._index_of(member)),
                self,
            )
            if image is not None:
                return flow.handle_image(conversation, image, caption=text)
            return flow.handle_text(conversation, text)

        if conversation.step == STEP_ADVISOR:
            from app.domain.advisor import AdvisorUnavailable
            from app.services.advisor import AdvisorService

            if text.startswith("/cancel"):
                self._clear_conversation(conversation)
                self._safe_send(
                    chat_id,
                    "پرسش لغو شد.",
                    inline_keyboard([[("منوی اصلی", "h")]]),
                )
                return True
            question = text.strip()[:600]
            if len(question) < 5:
                self._safe_send(chat_id, "سوال را کمی کامل تر بنویسید (حداقل ۵ کاراکتر).")
                return True
            member = next(
                (
                    item
                    for item in LicenseService.access_memberships(self.db, user)
                    if str(item.id) == str(conversation.payload.get("member_id"))
                ),
                None,
            )
            index = int((conversation.payload or {}).get("index") or 0)
            if member is None:
                self._clear_conversation(conversation)
                self._safe_send(chat_id, "دسترسی شما به این پروژه فعال نیست. لطفا /start را بزنید.")
                return True
            project = member.project
            context = "\n".join(
                part
                for part in (
                    f"نام پروژه: {project.name}" if project else "",
                    f"وضعیت پروژه: {project.status}" if project else "",
                    f"توضیح: {project.description}" if project and project.description else "",
                )
                if part
            )
            try:
                answer = AdvisorService.answer(question, context=context)
            except AdvisorUnavailable:
                self._clear_conversation(conversation)
                self._safe_send(
                    chat_id,
                    "مشاور هوشمند هنوز فعال نشده است. سوال خود را از بخش «پشتیبانی و تیکت» بپرسید.",
                    inline_keyboard(
                        [
                            [("پشتیبانی و تیکت", f"{index}:tickets")],
                            [("منوی اصلی", f"{index}:home")],
                        ]
                    ),
                )
                return True
            except Exception:  # noqa: BLE001 - provider errors never leak to chat
                logger.exception("Advisor call failed")
                self._clear_conversation(conversation)
                self._safe_send(
                    chat_id,
                    "در حال حاضر پاسخ به این سوال ممکن نشد. لطفا بعدا تلاش کنید یا از پشتیبانی بپرسید.",
                    inline_keyboard([[("منوی اصلی", f"{index}:home")]]),
                )
                return True
            self._clear_conversation(conversation)
            self._safe_send(
                chat_id,
                html_escape(answer),
                inline_keyboard(
                    [
                        [("پرسش دیگر", f"{index}:advice")],
                        [("منوی اصلی", f"{index}:home")],
                    ]
                ),
            )
            return True

        if text.startswith("/cancel"):
            self._clear_conversation(conversation)
            self._safe_send(chat_id, "ثبت تیکت لغو شد.", inline_keyboard([[("منوی اصلی", "h")]]))
            return True
        if text.startswith("/"):
            self._clear_conversation(conversation)
            return False

        now = utcnow()
        if conversation.expires_at < now:
            self._clear_conversation(conversation)
            self._safe_send(chat_id, "زمان تکمیل تیکت به پایان رسید. لطفا از منو دوباره شروع کنید.")
            return True

        member = next(
            (
                item
                for item in LicenseService.access_memberships(self.db, user)
                if str(item.id) == str(conversation.payload.get("member_id"))
            ),
            None,
        )
        if member is None:
            self._clear_conversation(conversation)
            self._safe_send(chat_id, "دسترسی شما به این پروژه فعال نیست. لطفا /start را بزنید.")
            return True

        if conversation.step == "ticket_subject":
            if image is not None and not text:
                self._safe_send(
                    chat_id, "ابتدا موضوع تیکت را بنویسید؛ سپس در مرحله بعد تصویر را بفرستید."
                )
                return True
            if len(text) < 3:
                self._safe_send(chat_id, "موضوع خیلی کوتاه است. یک موضوع واضح تر بنویسید.")
                return True
            conversation.step = "ticket_body"
            conversation.payload = {**conversation.payload, "subject": text[:200]}
            conversation.expires_at = now + timedelta(minutes=CONVERSATION_TTL_MINUTES)
            self.db.flush()
            self._safe_send(
                chat_id,
                "متن کامل تیکت را بنویسید. می توانید چند خط توضیح بدهید.",
                inline_keyboard([[("لغو", "cancel")]]),
            )
            return True

        attachment = self._download_image(chat_id, image) if image is not None else None
        if image is not None and attachment is None:
            return True

        if conversation.step == "ticket_reply":
            ticket_id = conversation.payload.get("ticket_id")
            try:
                ticket = TicketService.get(self.db, uuid.UUID(str(ticket_id)))
                if ticket.member_id != member.id:
                    raise ApiError(403, "forbidden", "این تیکت متعلق به شما نیست.")
                TicketService.reply(
                    self.db,
                    ticket=ticket,
                    body=text,
                    author_type="employer",
                    member=member,
                    actor=actor_for_employer(member),
                    channel="telegram",
                    attachments=[attachment] if attachment else None,
                )
                self.db.commit()
            except ApiError as exc:
                self.db.rollback()
                self._safe_send(chat_id, html_escape(exc.message))
                return True
            except Exception:  # noqa: BLE001
                self.db.rollback()
                logger.exception("Ticket reply from Telegram failed")
                self._safe_send(chat_id, "ارسال پاسخ انجام نشد. لطفا بعدا دوباره تلاش کنید.")
                return True
            self._clear_conversation(conversation)
            self._safe_send(
                chat_id,
                "پاسخ شما ثبت شد و برای تیم پشتیبانی ارسال می شود.",
                inline_keyboard([[("بازگشت به منو", f"{self._index_of(member)}:home")]]),
            )
            return True

        if conversation.step == "ticket_body":
            subject = str(conversation.payload.get("subject") or "درخواست پشتیبانی")
            try:
                ticket = TicketService.create(
                    self.db,
                    project=member.project,
                    subject=subject,
                    body=text,
                    created_by_type="employer",
                    member=member,
                    admin_id=None,
                    actor=actor_for_employer(member),
                    channel="telegram",
                    attachments=[attachment] if attachment else None,
                )
                self.db.commit()
            except ApiError as exc:
                self.db.rollback()
                self._safe_send(chat_id, html_escape(exc.message))
                return True
            except Exception:  # noqa: BLE001
                self.db.rollback()
                logger.exception("Ticket creation from Telegram failed")
                self._safe_send(chat_id, "ثبت تیکت انجام نشد. لطفا بعدا دوباره تلاش کنید.")
                return True
            self._clear_conversation(conversation)
            self._safe_send(
                chat_id,
                "تیکت شما ثبت شد. پاسخ تیم پشتیبانی از طریق همین ربات اطلاع داده می شود.\n"
                f"شماره پیگیری: <code>{str(ticket.id)[:8]}</code>",
                inline_keyboard([[("بازگشت به منو", f"{self._index_of(member)}:home")]]),
            )
            return True

        self._clear_conversation(conversation)
        return False

    def _set_conversation(
        self, user: TelegramUser, member: ProjectMember, *, step: str, payload: dict
    ) -> None:
        from app.models.ticket import TelegramConversation

        now = utcnow()
        conversation = self.db.scalar(
            select(TelegramConversation).where(
                TelegramConversation.telegram_user_id == user.id,
                TelegramConversation.project_id == member.project_id,
            )
        )
        expires = now + timedelta(minutes=CONVERSATION_TTL_MINUTES)
        values = {
            "step": step,
            "payload": {**payload, "member_id": str(member.id)},
            "expires_at": expires,
            "completed": False,
            "updated_at": now,
        }
        if conversation is None:
            conversation = TelegramConversation(
                telegram_user_id=user.id,
                project_id=member.project_id,
                created_at=now,
                **values,
            )
            self.db.add(conversation)
        else:
            for key, value in values.items():
                setattr(conversation, key, value)
        self.db.flush()

    def _get_conversation(self, user: TelegramUser):
        from app.models.ticket import TelegramConversation

        return self.db.scalar(
            select(TelegramConversation)
            .where(
                TelegramConversation.telegram_user_id == user.id,
                TelegramConversation.completed.is_(False),
            )
            .order_by(TelegramConversation.updated_at.desc())
        )

    def _clear_conversation(self, conversation) -> None:
        self.db.delete(conversation)
        self.db.flush()

    def _index_of(self, member: ProjectMember) -> int:
        memberships = LicenseService.access_memberships(self.db, member.telegram_user)
        return next(
            (position for position, item in enumerate(memberships) if item.id == member.id), 0
        )

    # ------------------------------------------------------------------
    # Order intake and quick menu
    # ------------------------------------------------------------------
    def _order_flow(self, user: TelegramUser, chat_id: int = 0) -> OrderFlow:
        return OrderFlow(self.db, self.adapter, self.settings, user, chat_id)

    def _start_order(self, user: TelegramUser, chat_id: int) -> None:
        conversation = self._get_conversation(user)
        if conversation is not None:
            self._clear_conversation(conversation)
        self._order_flow(user, chat_id).start()

    def _cancel_flows(self, user: TelegramUser) -> None:
        """Drop any half-finished flow so the next text message is unambiguous."""
        self._order_flow(user).cancel()
        conversation = self._get_conversation(user)
        if conversation is not None:
            self._clear_conversation(conversation)

    def _cancel_command(self, user: TelegramUser, chat_id: int) -> None:
        flow = self._order_flow(user, chat_id)
        if flow.has_session():
            flow.cancel()
            self._safe_send(
                chat_id,
                "ثبت سفارش لغو شد. هر زمان خواستید از دکمه «ثبت سفارش» دوباره شروع کنید.",
                inline_keyboard([[("منوی اصلی", "h")]]),
            )
            return
        conversation = self._get_conversation(user)
        if conversation is not None:
            self._clear_conversation(conversation)
            self._safe_send(chat_id, "عملیات جاری لغو شد.", inline_keyboard([[("منوی اصلی", "h")]]))
            return
        self._safe_send(
            chat_id,
            "عملیات در حال انجامی وجود ندارد.",
            inline_keyboard([[("منوی اصلی", "h")]]),
        )

    def _send_help(self, chat_id: int) -> None:
        self._safe_send(
            chat_id,
            HELP,
            inline_keyboard([[("ثبت سفارش", "o:home")], [("نمایش منو", "h")]]),
        )

    def _send_portfolio(self, chat_id: int) -> None:
        """Portfolio index. Texts are edited from the panel, never hard-coded."""
        categories = CatalogService.public_tree(self.db)
        rows: list[list[tuple[str, str]]] = [
            [((f"{category.emoji} {category.title}").strip(), f"op:{index}")]
            for index, category in enumerate(categories)
            if category.show_portfolio
        ]
        if not rows:
            self._safe_send(
                chat_id,
                "در حال حاضر نمونه کار منتشر شده ای برای نمایش وجود ندارد.\n"
                "با ثبت سفارش، نمونه کارهای مرتبط با نیاز شما برایتان ارسال می شود.",
                inline_keyboard([[("ثبت سفارش", "o:home")], [("منوی اصلی", "h")]]),
            )
            return
        self._safe_send(
            chat_id,
            "<b>نمونه کارها</b>\n\nدسته مورد نظر را انتخاب کنید تا نمونه کارهای آن را ببینید.\n"
            "<i>محتوای هر دسته از پنل مدیریت قابل ویرایش است.</i>",
            inline_keyboard(rows + [[("ثبت سفارش", "o:home")]]),
        )

    def _ensure_menu_keyboard(
        self, user: TelegramUser, chat_id: int, *, force: bool = False
    ) -> None:
        """Send the persistent reply keyboard once (it then stays on screen)."""
        now = utcnow()
        last = user.menu_keyboard_sent_at
        if not force and last is not None and (now - last) < timedelta(days=30):
            return
        self._safe_send(
            chat_id,
            "برای دسترسی سریع، از دکمه های پایین صفحه استفاده کنید.",
            reply_keyboard(
                [[ORDER_BUTTON], [MENU_BUTTON, HELP_BUTTON]],
                placeholder="یکی از گزینه ها را انتخاب کنید",
            ),
        )
        user.menu_keyboard_sent_at = now
        self.db.flush()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _upsert_user(self, sender: dict) -> TelegramUser:
        return TelegramUserRepository.upsert(
            self.db,
            telegram_id=int(sender["id"]),
            username=sender.get("username"),
            first_name=sender.get("first_name"),
            last_name=sender.get("last_name"),
            now=utcnow(),
        )

    def _record_update(self, update: dict) -> None:
        now = utcnow()
        state = self.db.get(SystemState, "telegram_last_update_at")
        value = {
            "at": now.isoformat(),
            "update_id": update.get("update_id"),
        }
        if state is None:
            state = SystemState(key="telegram_last_update_at", value=value, updated_at=now)
            self.db.add(state)
        else:
            state.value = value
            state.updated_at = now
        self.db.flush()

    def _safe_send(self, chat_id: int, text: str, keyboard: dict | None = None) -> None:
        try:
            self.adapter.send_message(chat_id, text, keyboard)
        except TelegramError as exc:
            logger.warning("Telegram send failed for chat %s: %s", chat_id, type(exc).__name__)

    # ------------------------------------------------------------------
    # Used by the worker after an admin approves a membership
    # ------------------------------------------------------------------
    @staticmethod
    def send_approval_welcome(
        db: Session,
        adapter: TelegramAdapter,
        settings: Settings,
        *,
        member: ProjectMember,
        chat_id: int,
    ) -> None:
        project = member.project
        flags = {feature.key: feature.enabled for feature in project.features}
        memberships = LicenseService.access_memberships(db, member.telegram_user)
        index = next(
            (position for position, item in enumerate(memberships) if item.id == member.id), 0
        )
        text = (
            f"اتصال شما به پروژه <b>{html_escape(project.name)}</b> تایید شد.\n\n"
            "از این پس اطلاعیه ها و وضعیت مالی پروژه را از همین ربات دریافت می کنید."
        )
        enabled = enabled_features(flags)
        keyboard = (
            project_menu_buttons(index, flags)
            if enabled
            else inline_keyboard([[("راهنما", "help")]])
        )
        # Errors propagate so the worker can classify them: transient errors are
        # retried, unknown outcomes are not (duplicate risk).
        adapter.send_message(chat_id, truncate_html(text), keyboard)
