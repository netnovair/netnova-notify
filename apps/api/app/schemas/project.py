from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import ProjectStatus
from app.domain.features import FEATURES
from app.features import all_features
from app.schemas.common import ORMModel
from app.schemas.license import LicenseOut
from app.schemas.member import MemberOut


class FeatureOut(BaseModel):
    key: str
    label: str
    description: str
    enabled: bool
    implemented: bool
    settings: dict = {}


class ProjectChannelOut(BaseModel):
    channel: str
    label: str
    enabled: bool
    configured: bool
    mode: str
    beta: bool
    recipient_hint: str
    settings: dict = {}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(default=None, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    client_name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    features: dict[str, bool] | None = None

    @field_validator("name", "client_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("features")
    @classmethod
    def _known_features(cls, value: dict[str, bool] | None) -> dict[str, bool] | None:
        if value is None:
            return None
        unknown = set(value) - set(FEATURES)
        if unknown:
            raise ValueError(f"Unknown feature keys: {sorted(unknown)}")
        return value


class ProjectFeaturesUpdate(BaseModel):
    #: Full desired map; omitted keys keep their current value.
    features: dict[str, bool]

    @field_validator("features")
    @classmethod
    def _known(cls, value: dict[str, bool]) -> dict[str, bool]:
        unknown = set(value) - set(FEATURES)
        if unknown:
            raise ValueError(f"Unknown feature keys: {sorted(unknown)}")
        return value


class ProjectChannelUpdate(BaseModel):
    enabled: bool
    settings: dict | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    client_name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    status: ProjectStatus | None = None
    features: dict[str, bool] | None = None

    @field_validator("name", "client_name")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("features")
    @classmethod
    def _known_features(cls, value: dict[str, bool] | None) -> dict[str, bool] | None:
        if value is None:
            return None
        unknown = set(value) - set(FEATURES)
        if unknown:
            raise ValueError(f"Unknown feature keys: {sorted(unknown)}")
        return value


class ProjectOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    client_name: str
    description: str | None
    status: str
    is_demo: bool
    telegram_connected_at: datetime | None
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    features: list[FeatureOut]
    channels: list[ProjectChannelOut] = []
    license: LicenseOut | None = None
    members: list[MemberOut] = []
    open_payments_count: int = 0
    notifications_count: int = 0


class ProjectCreated(ProjectOut):
    license_code: str | None = None


class ProjectListItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    client_name: str
    status: str
    is_demo: bool
    archived_at: datetime | None = None
    created_at: datetime
    telegram_connected: bool
    telegram_connected_at: datetime | None
    employer: MemberOut | None
    license_status: str | None
    license_expires_at: datetime | None
    enabled_features: list[str]
    open_payments_count: int
    notifications_count: int
    open_tickets: int = 0


def feature_outputs(
    flags: dict[str, bool], settings: dict[str, dict] | None = None
) -> list[FeatureOut]:
    settings = settings or {}
    return [
        FeatureOut(
            key=definition.key,
            label=definition.label,
            description=definition.description,
            enabled=flags.get(definition.key, definition.default_enabled),
            implemented=definition.implemented,
            settings=settings.get(definition.key, {}),
        )
        for definition in all_features()
    ]
