"""Employer-facing capability registry.

A *feature* is one button in the employer's Telegram menu plus the code that
serves it. Features are enabled per project in the admin panel, so the same
central bot shows a different menu for each employer.

Adding a capability (for example an invoice builder):

1. create ``app/features/invoice.py``;
2. define ``FEATURE = FeatureDefinition(key="invoice", ...)``;
3. write a handler ``def handle(ctx: FeatureContext) -> None``;
4. register both in ``app/features/__init__.py``.

No database migration is required: ``project_features.key`` is a plain string and
``settings`` is JSONB, so new features can carry their own configuration. The
admin panel reads the catalog from ``GET /api/v1/features`` and renders the
toggle automatically.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy.orm import Session

    from app.adapters.telegram.base import TelegramAdapter
    from app.core.config import Settings
    from app.models.telegram import ProjectMember


@dataclass(frozen=True)
class FeatureDefinition:
    key: str
    label: str
    description: str
    #: False means the button answers with an explicit "coming soon" message.
    implemented: bool
    default_enabled: bool
    order: int
    #: Callback suffix, e.g. ``ann`` -> ``<project>:ann``. Never an id.
    action: str | None
    #: Optional JSON-schema-like description used by the admin UI (informational).
    settings_schema: dict[str, Any] = field(default_factory=dict)

    @property
    def callback(self) -> str | None:
        return f"m:{self.action}" if self.action else None


class _BotProtocol(Protocol):
    def send_announcements(self, chat_id: int, member: ProjectMember, index: int) -> None: ...

    def send_financial(self, chat_id: int, member: ProjectMember, index: int) -> None: ...

    def send_tickets(self, chat_id: int, member: ProjectMember, index: int) -> None: ...


@dataclass
class FeatureContext:
    db: Session
    adapter: TelegramAdapter
    settings: Settings
    chat_id: int
    member: ProjectMember
    index: int
    bot: _BotProtocol


FeatureHandler = Callable[[FeatureContext], None]


@dataclass(frozen=True)
class RegisteredFeature:
    definition: FeatureDefinition
    handler: FeatureHandler | None = None


_REGISTRY: dict[str, RegisteredFeature] = {}


def register(definition: FeatureDefinition, handler: FeatureHandler | None = None) -> None:
    if definition.key in _REGISTRY:
        raise RuntimeError(f"Feature '{definition.key}' is already registered")
    if definition.implemented and handler is None:
        raise RuntimeError(f"Implemented feature '{definition.key}' needs a handler")
    _REGISTRY[definition.key] = RegisteredFeature(definition=definition, handler=handler)


def all_features() -> list[FeatureDefinition]:
    return sorted((item.definition for item in _REGISTRY.values()), key=lambda item: item.order)


def get_feature(key: str) -> FeatureDefinition | None:
    item = _REGISTRY.get(key)
    return item.definition if item else None


def handler_for(key: str) -> FeatureHandler | None:
    item = _REGISTRY.get(key)
    return item.handler if item else None


def find_by_action(action: str) -> RegisteredFeature | None:
    for item in _REGISTRY.values():
        if item.definition.action == action:
            return item
    return None


def enabled_features(flags: dict[str, bool]) -> list[FeatureDefinition]:
    """Enabled, ordered menu entries for one project.

    Unknown keys in ``flags`` are ignored (a feature can be retired while its row
    still exists in older databases).
    """
    result: list[FeatureDefinition] = []
    for definition in all_features():
        if flags.get(definition.key, definition.default_enabled):
            result.append(definition)
    return result
