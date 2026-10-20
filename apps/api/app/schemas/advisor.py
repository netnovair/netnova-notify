from __future__ import annotations

from pydantic import BaseModel, Field


class AdvisorStatusOut(BaseModel):
    available: bool
    provider: str
    model: str
    reason: str


class AdvisorAsk(BaseModel):
    question: str = Field(min_length=2, max_length=600)


class AdvisorAnswer(BaseModel):
    answer: str
