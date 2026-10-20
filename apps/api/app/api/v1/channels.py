from __future__ import annotations

from fastapi import APIRouter, Depends

from app.adapters.messaging.registry import channel_catalog
from app.api.deps import AdminContext, get_admin_context
from app.features import all_features
from app.schemas.admin import ChannelStateOut, FeatureCatalogItem

router = APIRouter(tags=["catalog"])


@router.get("/channels", response_model=list[ChannelStateOut])
def list_channels(_: AdminContext = Depends(get_admin_context)) -> list[ChannelStateOut]:
    """Provider catalog with honest configuration state (no secrets)."""
    return [ChannelStateOut(**state) for state in channel_catalog()]


@router.get("/features", response_model=list[FeatureCatalogItem])
def list_features(_: AdminContext = Depends(get_admin_context)) -> list[FeatureCatalogItem]:
    """Capability catalog; the admin UI renders project toggles from this list."""
    return [
        FeatureCatalogItem(
            key=definition.key,
            label=definition.label,
            description=definition.description,
            implemented=definition.implemented,
            default_enabled=definition.default_enabled,
            action=definition.action,
            settings_schema=definition.settings_schema,
        )
        for definition in all_features()
    ]
