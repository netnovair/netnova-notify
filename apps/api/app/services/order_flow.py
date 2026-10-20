"""Telegram conversation that collects a pre-sales order.

Design constraints:

* it must work for visitors who have no license and no project;
* callback data only carries list indices (``oc:1``, ``oi:0:2``) that are
  re-resolved on the server against the *current* catalog, so a stale button can
  never address a different service;
* every answer is validated server-side - the Telegram client is never trusted;
* the session lives in ``order_sessions`` and expires, so an abandoned flow does
  not block the user forever.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.telegram.base import TelegramAdapter, TelegramError
from app.adapters.telegram.formatting import html_escape, inline_keyboard, truncate
from app.core.config import Settings
from app.core.security import utcnow
from app.models.catalog import OrderSession, ServiceCategory, ServiceItem
from app.models.telegram import TelegramUser
from app.services.catalog import CatalogService
from app.services.orders import OrderService, fa_digits, normalize_phone, validate_answer

logger = logging.getLogger(__name__)

ORDER_BUTTON = "ثبت سفارش"
MENU_BUTTON = "منوی من"
HELP_BUTTON = "راهنما"
CANCEL_BUTTON = "لغو"

SESSION_TTL_MINUTES = 45
MAX_ANSWERS = 40
MAX_NAME = 80


class OrderFlow:
    def __init__(
        self,
        db: Session,
        adapter: TelegramAdapter,
        settings: Settings,
        user: TelegramUser,
        chat_id: int,
    ) -> None:
        self.db = db
        self.adapter = adapter
        self.settings = settings
        self.user = user
        self.chat_id = chat_id

    # ------------------------------------------------------------------
    # Session state
    # ------------------------------------------------------------------
    def _session(self) -> OrderSession | None:
        session = self.db.scalar(
            select(OrderSession).where(OrderSession.telegram_user_id == self.user.id)
        )
        if session is None:
            return None
        if session.expires_at and session.expires_at < utcnow():
            self.db.delete(session)
            self.db.flush()
            return None
        return session

    def has_session(self) -> bool:
        return self._session() is not None

    def _save(self, *, step: str, payload: dict) -> OrderSession:
        now = utcnow()
        session = self._session()
        expires = now + timedelta(minutes=SESSION_TTL_MINUTES)
        if session is None:
            session = OrderSession(
                telegram_user_id=self.user.id,
                step=step,
                payload=payload,
                expires_at=expires,
                created_at=now,
                updated_at=now,
            )
            self.db.add(session)
        else:
            session.step = step
            session.payload = payload
            session.expires_at = expires
            session.updated_at = now
        self.db.flush()
        return session

    def cancel(self) -> None:
        session = self._session()
        if session is not None:
            self.db.delete(session)
            self.db.flush()

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------
    def start(self) -> None:
        self.cancel()
        categories = CatalogService.public_tree(self.db)
        if not categories:
            self._send(
                "در حال حاضر خدمتی برای ثبت سفارش تعریف نشده است. "
                "لطفا بعدا دوباره سر بزنید یا با پشتیبانی تماس بگیرید.",
                inline_keyboard([[("منوی اصلی", "h")]]),
            )
            return
        rows = [
            [(f"{category.emoji} {category.title}".strip(), f"oc:{index}")]
            for index, category in enumerate(categories)
        ]
        self._send(
            "<b>ثبت سفارش</b>\n\n"
            "برای اینکه بهترین پیشنهاد را بدهیم، ابتدا دسته خدمت مورد نظر را انتخاب کنید.\n"
            "در هر مرحله با دکمه های نمایش داده شده جلو بروید. با /cancel هم می توانید "
            "لغو کنید.",
            inline_keyboard(rows),
        )

    def handle_callback(self, data: str) -> bool:
        if data == "o:home":
            self.cancel()
            self.start()
            return True
        if data == "ox":
            self.cancel()
            self._send(
                "ثبت سفارش لغو شد. هر وقت خواستید از دکمه «ثبت سفارش» شروع کنید.",
                inline_keyboard([[("منوی اصلی", "h")]]),
            )
            return True
        if data.startswith("oc:") and data[3:].isdigit():
            self._show_category(int(data[3:]))
            return True
        if data.startswith("op:") and data[3:].isdigit():
            self._show_portfolio(int(data[3:]))
            return True
        if data.startswith("oi:") and data.count(":") == 2:
            _, _, rest = data.partition(":")
            category_index, _, item_index = rest.partition(":")
            if category_index.isdigit() and item_index.isdigit():
                self._start_item(int(category_index), int(item_index))
                return True
            return False
        if data.startswith("oq:") and data.count(":") == 2:
            _, _, rest = data.partition(":")
            question_index, _, option_index = rest.partition(":")
            if question_index.isdigit() and option_index.isdigit():
                self._answer_option(int(question_index), int(option_index))
                return True
            return False
        if data == "opf":
            self._show_item_portfolio()
            return True
        if data == "oback":
            self._ask_question()
            return True
        if data == "oskip":
            self._skip_question()
            return True
        if data == "osubmit":
            self._submit()
            return True
        return False

    def handle_text(self, text: str) -> bool:
        session = self._session()
        if session is None:
            return False
        if text.startswith("/cancel") or text == CANCEL_BUTTON:
            self.cancel()
            self._send(
                "ثبت سفارش لغو شد. با دکمه «ثبت سفارش» می توانید دوباره شروع کنید.",
                inline_keyboard([[("منوی اصلی", "h")]]),
            )
            return True
        if text.startswith("/"):
            # Any other command abandons the flow instead of being stored as an answer.
            self.cancel()
            return False

        if session.step == "contact_name":
            self._collect_name(session, text)
            return True
        if session.step == "contact_phone":
            self._collect_phone(session, text)
            return True
        if session.step == "question":
            self._collect_answer(session, text)
            return True
        if session.step == "confirm":
            self._send(
                "برای ثبت نهایی، یکی از دکمه های زیر را انتخاب کنید.",
                inline_keyboard([[("ثبت نهایی سفارش", "osubmit")], [("لغو", "ox")]]),
            )
            return True
        return False

    # ------------------------------------------------------------------
    # Catalog navigation
    # ------------------------------------------------------------------
    def _show_category(self, index: int) -> None:
        categories = CatalogService.public_tree(self.db)
        if not 0 <= index < len(categories):
            self._send("این دسته در دسترس نیست. لطفا دوباره «ثبت سفارش» را بزنید.")
            return
        category = categories[index]
        lines = [f"<b>{html_escape(category.title)}</b>"]
        if category.description:
            lines.append(html_escape(category.description))
        lines.append("")
        lines.append("کدام خدمت را نیاز دارید؟")
        rows: list[list[tuple[str, str]]] = [
            [(item.title, f"oi:{index}:{position}")] for position, item in enumerate(category.items)
        ]
        if category.show_portfolio:
            rows.append([("مشاهده نمونه کارها", f"op:{index}")])
        rows.append([("بازگشت به دسته ها", "o:home")])
        self._send(truncate("\n".join(lines)), inline_keyboard(rows))

    def _show_portfolio(self, index: int) -> None:
        categories = CatalogService.public_tree(self.db)
        if not 0 <= index < len(categories):
            self._send("این دسته در دسترس نیست.")
            return
        category = categories[index]
        text = category.portfolio_text.strip() or "برای این بخش نمونه کاری ثبت نشده است."
        self._send_portfolio_entry(
            title=f"نمونه کارهای {category.title}",
            text=text,
            photo_url=category.portfolio_url,
            keyboard=inline_keyboard([[("بازگشت", f"oc:{index}")]]),
        )

    def _resolve_item(self, session: OrderSession) -> tuple[ServiceCategory, ServiceItem] | None:
        try:
            item_id = uuid.UUID(str(session.payload.get("item_id")))
        except (ValueError, TypeError):
            return None
        item = self.db.get(ServiceItem, item_id)
        if item is None or not item.is_active:
            return None
        category = item.category
        if category is None or not category.is_active:
            return None
        return category, item

    def _start_item(self, category_index: int, item_index: int) -> None:
        categories = CatalogService.public_tree(self.db)
        if not 0 <= category_index < len(categories):
            self._send("این خدمت در دسترس نیست. لطفا دوباره «ثبت سفارش» را بزنید.")
            return
        category = categories[category_index]
        if not 0 <= item_index < len(category.items):
            self._send("این زیرخدمت در دسترس نیست. لطفا دوباره انتخاب کنید.")
            return
        item = category.items[item_index]
        payload = {
            "category_id": str(category.id),
            "item_id": str(item.id),
            "answers": [],
            "question_index": 0,
            "contact_name": self.user.contact_name or "",
            "contact_phone": self.user.contact_phone or "",
        }
        if item.description:
            self._send(f"<b>{html_escape(item.title)}</b>\n\n{html_escape(item.description)}")

        if not self.user.contact_name:
            self._save(step="contact_name", payload=payload)
            self._ask_name()
            return
        if not self.user.contact_phone:
            self._save(step="contact_phone", payload=payload)
            self._ask_phone()
            return
        payload["contact_name"] = self.user.contact_name
        payload["contact_phone"] = self.user.contact_phone
        self._save(step="question", payload=payload)
        self._ask_question()

    # ------------------------------------------------------------------
    # Contact details
    # ------------------------------------------------------------------
    def _ask_name(self) -> None:
        self._send(
            "برای شروع، نام و نام خانوادگی خود را بنویسید.\n"
            "<i>این اطلاعات فقط برای تماس کارشناسان ما استفاده می شود.</i>",
            inline_keyboard([[("لغو", "ox")]]),
        )

    def _ask_phone(self) -> None:
        self._send(
            "شماره تماس خود را بنویسید. نمونه: <code>09121234567</code>\n"
            "<i>فقط برای هماهنگی همین سفارش استفاده می شود.</i>",
            inline_keyboard([[("لغو", "ox")]]),
        )

    def _collect_name(self, session: OrderSession, text: str) -> None:
        name = " ".join(text.split())
        if len(name) < 3 or len(name) > MAX_NAME:
            self._send("نام و نام خانوادگی را کامل تر بنویسید (حداقل ۳ حرف).")
            return
        if any(char.isdigit() for char in name):
            self._send("نام نباید شامل عدد باشد. لطفا دوباره بنویسید.")
            return
        payload = {**session.payload, "contact_name": name}
        self.user.contact_name = name
        self._save(step="contact_phone", payload=payload)
        self._ask_phone()

    def _collect_phone(self, session: OrderSession, text: str) -> None:
        phone = normalize_phone(text)
        if phone is None:
            self._send(
                "شماره معتبر نیست. یک شماره موبایل ایران با ۰۹ شروع کنید؛ "
                "نمونه: <code>09121234567</code>"
            )
            return
        payload = {**session.payload, "contact_phone": phone}
        self.user.contact_phone = phone
        self._save(step="question", payload=payload)
        self._send("ممنون. حالا چند سوال کوتاه درباره سفارش شما می پرسیم.")
        self._ask_question()

    # ------------------------------------------------------------------
    # Questions
    # ------------------------------------------------------------------
    def _active_questions(self, session: OrderSession):
        resolved = self._resolve_item(session)
        if resolved is None:
            return []
        _, item = resolved
        return [question for question in item.questions if question.is_active]

    def _ask_question(self) -> None:
        session = self._session()
        if session is None:
            return
        resolved = self._resolve_item(session)
        if resolved is None:
            self.cancel()
            self._send("این خدمت دیگر در دسترس نیست. لطفا از ابتدا شروع کنید.")
            return
        questions = self._active_questions(session)
        index = int(session.payload.get("question_index", 0))
        if index >= len(questions):
            self._show_summary(session)
            return
        question = questions[index]
        total = len(questions)
        lines = [
            f"<b>سوال {fa_digits(index + 1)} از {fa_digits(total)}</b>",
            "",
            html_escape(question.label),
        ]
        if question.help_text:
            lines.append(f"<i>{html_escape(question.help_text)}</i>")
        rows: list[list[tuple[str, str]]] = []
        if question.field_type == "choice":
            options = [str(option) for option in (question.options or [])]
            rows = [[(option, f"oq:{index}:{position}")] for position, option in enumerate(options)]
        if not question.required:
            rows.append([("این مورد را رد کن", "oskip")])
        _, item = resolved
        # Only on the first question: keeps later screens short while the
        # sample-work button stays reachable from the start of the flow.
        if item.show_portfolio and index == 0:
            rows.append([("نمونه کارهای این خدمت", "opf")])
        rows.append([("لغو سفارش", "ox")])
        self._send(truncate("\n".join(lines)), inline_keyboard(rows))

    def _show_item_portfolio(self) -> None:
        session = self._session()
        if session is None:
            self._send("این بخش در دسترس نیست. لطفا «ثبت سفارش» را دوباره بزنید.")
            return
        resolved = self._resolve_item(session)
        if resolved is None:
            self._send("این خدمت دیگر در دسترس نیست.")
            return
        _, item = resolved
        text = item.portfolio_text.strip()
        if not text:
            text = (
                "برای این خدمت هنوز نمونه کاری در ربات منتشر نشده است. "
                "پس از ثبت سفارش، کارشناسان نت نووا نمونه های مرتبط را برای شما ارسال می کنند."
            )
        self._send_portfolio_entry(
            title=f"نمونه کارهای {item.title}",
            text=text,
            photo_url=item.portfolio_url,
            keyboard=inline_keyboard([[("ادامه سفارش", "oback")], [("لغو سفارش", "ox")]]),
        )

    def _answer_option(self, question_index: int, option_index: int) -> None:
        session = self._session()
        if session is None or session.step != "question":
            self._send("این سوال دیگر فعال نیست. لطفا «ثبت سفارش» را دوباره بزنید.")
            return
        questions = self._active_questions(session)
        if not 0 <= question_index < len(questions):
            self._send("این گزینه در دسترس نیست.")
            return
        question = questions[question_index]
        options = [str(option) for option in (question.options or [])]
        if not 0 <= option_index < len(options):
            self._send("این گزینه در دسترس نیست.")
            return
        self._store_answer(session, questions, question, options[option_index])

    def _collect_answer(self, session: OrderSession, text: str) -> None:
        questions = self._active_questions(session)
        index = int(session.payload.get("question_index", 0))
        if not 0 <= index < len(questions):
            self._show_summary(session)
            return
        resolved = self._resolve_item(session)
        if resolved is None:
            self.cancel()
            self._send("این خدمت دیگر در دسترس نیست. لطفا از ابتدا شروع کنید.")
            return
        question = questions[index]
        value, error = validate_answer(resolved[1], question, text)
        if error:
            self._send(html_escape(error))
            return
        self._store_answer(session, questions, question, value)

    def _skip_question(self) -> None:
        session = self._session()
        if session is None:
            return
        questions = self._active_questions(session)
        index = int(session.payload.get("question_index", 0))
        if not 0 <= index < len(questions) or questions[index].required:
            self._send("این سوال الزامی است و قابل رد کردن نیست.")
            return
        self._store_answer(session, questions, questions[index], None)

    def _store_answer(self, session: OrderSession, questions, question, value) -> None:
        answers = [
            item for item in session.payload.get("answers", []) if item.get("key") != question.key
        ]
        if value is not None:
            answers.append({"key": question.key, "label": question.label, "value": str(value)})
        if len(answers) > MAX_ANSWERS:
            self.cancel()
            self._send("تعداد پاسخ ها بیش از حد مجاز است. لطفا دوباره شروع کنید.")
            return
        payload = {
            **session.payload,
            "answers": answers,
            "question_index": int(session.payload.get("question_index", 0)) + 1,
        }
        self._save(step="question", payload=payload)
        if payload["question_index"] >= len(questions):
            self._show_summary(self._session())
        else:
            self._ask_question()

    # ------------------------------------------------------------------
    # Summary and submit
    # ------------------------------------------------------------------
    def _summary_text(self, session: OrderSession) -> str:
        resolved = self._resolve_item(session)
        item_title = resolved[1].title if resolved else "—"
        category_title = resolved[0].title if resolved else "—"
        lines = [
            "<b>بازبینی سفارش</b>",
            "",
            f"دسته: {html_escape(category_title)}",
            f"خدمت: {html_escape(item_title)}",
            f"نام: {html_escape(str(session.payload.get('contact_name', '')))}",
            f"تماس: {html_escape(str(session.payload.get('contact_phone', '')))}",
            "",
        ]
        answers = session.payload.get("answers", [])
        if answers:
            lines.append("<b>پاسخ های شما</b>")
            for answer in answers:
                lines.append(
                    f"• {html_escape(str(answer.get('label')))}: {html_escape(str(answer.get('value')))}"
                )
        lines.append("")
        lines.append("<i>با ثبت نهایی، کارشناسان نت نووا با شما تماس می گیرند.</i>")
        return truncate("\n".join(lines))

    def _show_summary(self, session: OrderSession | None) -> None:
        if session is None:
            return
        self._save(step="confirm", payload=session.payload)
        self._send(
            self._summary_text(session),
            inline_keyboard([[("ثبت نهایی سفارش", "osubmit")], [("لغو", "ox")]]),
        )

    def _submit(self) -> None:
        session = self._session()
        if session is None:
            self._send("سفارشی برای ثبت وجود ندارد. لطفا از ابتدا شروع کنید.")
            return
        resolved = self._resolve_item(session)
        if resolved is None:
            self.cancel()
            self._send("این خدمت دیگر در دسترس نیست. لطفا از ابتدا شروع کنید.")
            return
        category, item = resolved
        from app.services.audit import Actor

        try:
            request = OrderService.create(
                self.db,
                category_id=category.id,
                item=item,
                contact_name=str(session.payload.get("contact_name", "")),
                contact_phone=str(session.payload.get("contact_phone", "")),
                answers=list(session.payload.get("answers", [])),
                telegram_user_id=self.user.id,
                telegram_username=self.user.username,
                telegram_id=self.user.telegram_id,
                actor=Actor(
                    type="telegram_user",
                    id=self.user.id,
                    label=self.user.username or str(self.user.telegram_id),
                ),
            )
            self.db.delete(session)
            self.db.commit()
        except Exception:  # noqa: BLE001 - never show internals to the visitor
            self.db.rollback()
            logger.exception("Failed to store a service request")
            self._send("ثبت سفارش انجام نشد. لطفا چند دقیقه بعد دوباره تلاش کنید.")
            return

        self._send(
            "<b>سفارش شما ثبت شد ✅</b>\n\n"
            f"شماره پیگیری: <code>{str(request.id)[:8]}</code>\n"
            f"خدمت: {html_escape(item.title)}\n\n"
            "کارشناسان نت نووا در ساعات کاری با شما تماس می گیرند.",
            inline_keyboard([[("منوی اصلی", "h")]]),
        )
        self._notify_admin(request)

    def _notify_admin(self, request) -> None:
        chat_id = self.settings.admin_telegram_chat_id
        if not chat_id:
            return
        lines = [
            "<b>سفارش جدید</b>",
            f"خدمت: {html_escape(request.item_title)}",
            f"دسته: {html_escape(request.category_title)}",
            f"نام: {html_escape(request.contact_name)}",
            f"تماس: <code>{html_escape(request.contact_phone)}</code>",
        ]
        if request.telegram_username:
            lines.append(f"تلگرام: @{html_escape(request.telegram_username)}")
        for answer in (request.answers or [])[:10]:
            lines.append(
                f"• {html_escape(str(answer.get('label')))}: {html_escape(str(answer.get('value')))}"
            )
        lines.append("")
        lines.append(f"شماره پیگیری: <code>{str(request.id)[:8]}</code>")
        try:
            self.adapter.send_message(chat_id, truncate("\n".join(lines)))
        except TelegramError:
            logger.warning("Could not notify the admin about a new service request.")

    # ------------------------------------------------------------------
    def _send_portfolio_entry(
        self,
        *,
        title: str,
        text: str,
        photo_url: str,
        keyboard: dict | None = None,
    ) -> None:
        """Send the portfolio text, plus the sample image when the panel set one."""
        body = f"<b>{html_escape(title)}</b>\n\n{html_escape(text)}"
        if photo_url:
            try:
                self.adapter.send_photo_url(self.chat_id, photo_url, truncate(body, 900))
                self._send("برای ادامه یکی از گزینه ها را انتخاب کنید.", keyboard)
                return
            except TelegramError:
                logger.warning("Portfolio photo could not be sent; falling back to text.")
        self._send(truncate(body), keyboard)

    def _send(self, text: str, keyboard: dict | None = None) -> None:
        try:
            self.adapter.send_message(self.chat_id, text, keyboard)
        except TelegramError:
            logger.warning("Order flow could not send a message to chat %s", self.chat_id)
