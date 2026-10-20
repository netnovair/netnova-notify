"""Employer-facing AI advisor with a pluggable provider.

Phase decision: the structure is complete but no key is configured. Until an
``AI_ADVISOR_API_KEY`` exists, :meth:`AdvisorService.status` reports
``available=False`` and :meth:`AdvisorService.answer` raises
:class:`AdvisorUnavailable` — the bot answers «به زودی» and never improvises.

Only the employer's own project facts are passed as context (name, status,
progress-free descriptive fields). Money, license codes and Telegram identifiers
never reach the provider.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import Settings, get_settings
from app.domain.advisor import (
    SYSTEM_PROMPT,
    AdvisorStatus,
    AdvisorUnavailable,
    build_prompt,
    clean_answer,
)

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AdvisorService:
    @staticmethod
    def settings() -> Settings:
        return get_settings()

    @staticmethod
    def status(settings: Settings | None = None) -> AdvisorStatus:
        settings = settings or get_settings()
        if settings.ai_advisor_provider == "none":
            return AdvisorStatus(
                available=False,
                provider="none",
                model="",
                reason="ارائه دهنده مشاور تنظیم نشده است؛ قابلیت به زودی فعال می شود.",
            )
        if not settings.ai_advisor_api_key.strip():
            return AdvisorStatus(
                available=False,
                provider=settings.ai_advisor_provider,
                model=settings.ai_advisor_model,
                reason="کلید API مشاور تنظیم نشده است؛ قابلیت به زودی فعال می شود.",
            )
        return AdvisorStatus(
            available=True,
            provider=settings.ai_advisor_provider,
            model=settings.ai_advisor_model,
            reason="مشاور فعال است.",
        )

    @classmethod
    def answer(cls, question: str, *, context: str = "") -> str:
        status = cls.status()
        if not status.available:
            raise AdvisorUnavailable(status.reason)
        settings = cls.settings()
        if settings.ai_advisor_provider == "gemini":
            return cls._ask_gemini(settings, build_prompt(question, context=context))
        raise AdvisorUnavailable("ارائه دهنده مشاور پشتیبانی نمی شود.")

    @staticmethod
    def _ask_gemini(settings: Settings, prompt: str) -> str:
        url = GEMINI_ENDPOINT.format(model=settings.ai_advisor_model)
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 400,
            },
        }
        try:
            with httpx.Client(timeout=settings.ai_advisor_timeout_seconds) as client:
                response = client.post(
                    url,
                    # The key travels in a header, never in the URL, so it cannot
                    # end up in a proxy or access log.
                    headers={"x-goog-api-key": settings.ai_advisor_api_key},
                    json=payload,
                )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            # A provider outage must not surface as a 500 in the panel.
            logger.warning("Advisor provider call failed: %s", type(exc).__name__)
            raise AdvisorUnavailable(
                "ارتباط با سرویس مشاور برقرار نشد. لطفا بعدا تلاش کنید."
            ) from exc
        except ValueError as exc:  # non-JSON body
            logger.warning("Advisor provider returned an unreadable response")
            raise AdvisorUnavailable(
                "پاسخ سرویس مشاور قابل خواندن نبود. لطفا بعدا تلاش کنید."
            ) from exc
        candidates = data.get("candidates") or []
        if not candidates:
            logger.warning(
                "Advisor returned no candidates; finishReason=%s", data.get("promptFeedback")
            )
            raise AdvisorUnavailable("پاسخی از مشاور دریافت نشد. لطفا دوباره تلاش کنید.")
        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts)
        if not text.strip():
            raise AdvisorUnavailable("پاسخی از مشاور دریافت نشد. لطفا دوباره تلاش کنید.")
        return clean_answer(text)


__all__ = ["AdvisorService"]
