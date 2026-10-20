"""Backward-compatible facade over the feature plugin registry.

Historically features lived here as a hard-coded dictionary. They now live in
``app.features`` so a new capability can be added as a module. This module keeps
the old import names working for the API, schemas and the menu builder.
"""

from __future__ import annotations

from app.features import all_features, enabled_features, get_feature

#: key -> definition. ``FeatureKey`` (a StrEnum) hashes like its string value, so
#: ``FEATURES[FeatureKey.ANNOUNCEMENTS]`` keeps working.
FEATURES = {definition.key: definition for definition in all_features()}

SOON_CALLBACK_PREFIX = "s:"
IMPLEMENTED_MENU_CALLBACKS = {
    "m:home",
    "m:help",
    *(definition.callback for definition in FEATURES.values() if definition.callback),
}


def soon_message(key: str) -> str | None:
    definition = get_feature(key)
    if definition is None or definition.implemented:
        return None
    return f"قابلیت «{definition.label}» به زودی فعال می شود."


__all__ = [
    "FEATURES",
    "IMPLEMENTED_MENU_CALLBACKS",
    "SOON_CALLBACK_PREFIX",
    "enabled_features",
    "soon_message",
]
