"""Allow-list sanitizer for Telegram's HTML markup.

Everything the panel stores as "rich" text (announcement bodies, ticket replies,
message templates) is this small HTML subset. It is sanitized twice:

* when the admin saves it (the API never trusts the browser);
* when a message is rendered, because stored rows may predate a rule change.

Only the tags Telegram actually renders are kept. Everything else is escaped, so
a pasted ``<script>`` becomes visible text instead of live markup, and an
``<a>`` pointing at ``javascript:`` loses its link but keeps its label.
"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

MAX_LENGTH = 4096

#: Telegram Bot API HTML tags (https://core.telegram.org/bots/api#html-style).
ALLOWED_TAGS = {
    "b",
    "strong",
    "i",
    "em",
    "u",
    "ins",
    "s",
    "strike",
    "del",
    "a",
    "code",
    "pre",
    "blockquote",
    "tg-spoiler",
    "span",
}

_SIMPLE_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "tg-spoiler"}
_SAFE_HREF = re.compile(r"^https?://[^\s<>\"']+$", re.IGNORECASE)
_LANGUAGE_CLASS = re.compile(r"^language-[a-z0-9+#._-]{1,24}$", re.IGNORECASE)


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[str] = []
        self._pre_depth = 0

    # -- helpers -------------------------------------------------------
    def _open(self, text: str, tag: str) -> None:
        self.parts.append(text)
        self.stack.append(tag)

    def _close_to(self, tag: str) -> None:
        if tag not in self.stack:
            return
        while self.stack:
            current = self.stack.pop()
            if current == "pre":
                self._pre_depth = max(0, self._pre_depth - 1)
            self.parts.append(f"</{current}>")
            if current == tag:
                break

    # -- HTMLParser API -----------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = {name.lower(): (value or "") for name, value in attrs}
        if tag == "br":
            self.parts.append("\n")
            return
        if tag == "a":
            href = attributes.get("href", "")
            if not _SAFE_HREF.match(href):
                return
            self._open(f'<a href="{escape(href, quote=True)}">', "a")
            return
        if tag == "blockquote":
            self._open(
                "<blockquote expandable>" if "expandable" in attributes else "<blockquote>",
                "blockquote",
            )
            return
        if tag == "span":
            if attributes.get("class", "").strip().lower() == "tg-spoiler":
                self._open('<span class="tg-spoiler">', "span")
            return
        if tag == "pre":
            self._open("<pre>", "pre")
            self._pre_depth += 1
            return
        if tag in _SIMPLE_TAGS:
            # A language class is only meaningful inside a code block.
            if tag == "code" and self._pre_depth:
                language = attributes.get("class", "").strip()
                if _LANGUAGE_CLASS.match(language):
                    self._open(f'<code class="{language}">', "code")
                    return
            self._open(f"<{tag}>", tag)
            return
        # Unknown tags stay visible as text, never as markup.
        raw = f"<{tag}"
        for name, value in attrs:
            raw += f' {name}="{value}"' if value is not None else f" {name}"
        self.parts.append(escape(raw + ">"))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "br":
            self.parts.append("\n")
            return
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "br":
            return
        if tag in ALLOWED_TAGS:
            self._close_to(tag)
        else:
            self.parts.append(escape(f"</{tag}>"))

    def handle_data(self, data: str) -> None:
        self.parts.append(escape(data, quote=False))

    def result(self) -> str:
        while self.stack:
            current = self.stack.pop()
            self.parts.append(f"</{current}>")
        return "".join(self.parts)


def sanitize_telegram_html(value: str, *, limit: int = MAX_LENGTH) -> str:
    """Return a safe Telegram HTML string for ``value``.

    Plain text (no tags) is escaped, so the result is always safe to pass as the
    ``text`` of a ``sendMessage`` call with ``parse_mode=HTML``.
    """
    if not value:
        return ""
    parser = _Sanitizer()
    try:
        parser.feed(value)
        parser.close()
        cleaned = parser.result()
    except Exception:  # noqa: BLE001 - malformed markup must never break a send
        return escape(value, quote=False)
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 20].rstrip() + "…"
    return cleaned


_TAG_RE = re.compile(r"<[^>]+>")


def plain_text(value: str) -> str:
    """Flatten the allowed markup for SMS and other plain channels."""
    from html import unescape

    text = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|blockquote|pre)>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    return unescape(text).strip()


def has_markup(value: str) -> bool:
    return bool(_TAG_RE.search(value or ""))
