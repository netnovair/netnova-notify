"""AI advisor endpoints.

The panel calls ``GET /advisor/status`` to render the (currently disabled)
section honestly, and ``POST /advisor/ask`` only exists so the wiring is already
in place for the day a key is added.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import AdminContext, get_admin_context
from app.core.errors import conflict
from app.domain.advisor import AdvisorUnavailable
from app.schemas.advisor import AdvisorAnswer, AdvisorAsk, AdvisorStatusOut
from app.services.advisor import AdvisorService

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.get("/status", response_model=AdvisorStatusOut)
def advisor_status(_: AdminContext = Depends(get_admin_context)) -> AdvisorStatusOut:
    status = AdvisorService.status()
    return AdvisorStatusOut(
        available=status.available,
        provider=status.provider,
        model=status.model,
        reason=status.reason,
    )


@router.post("/ask", response_model=AdvisorAnswer)
def ask_advisor(
    payload: AdvisorAsk,
    _: AdminContext = Depends(get_admin_context),
) -> AdvisorAnswer:
    try:
        answer = AdvisorService.answer(payload.question)
    except AdvisorUnavailable as exc:
        raise conflict(str(exc), code="advisor_unavailable") from exc
    return AdvisorAnswer(answer=answer)
