"""Feature plugin bootstrap.

Import order matters only in that every module registers itself before the API
starts. Add new modules to ``register_all``.
"""

from __future__ import annotations

from app.features.base import (
    FeatureContext,
    FeatureDefinition,
    all_features,
    enabled_features,
    find_by_action,
    get_feature,
    handler_for,
    register,
)
from app.features.builtin import register_builtin

_LOADED = False


def register_all() -> None:
    global _LOADED
    if _LOADED:
        return
    register_builtin()
    # Import additional feature modules here, for example:
    # from app.features import invoice  # noqa: F401
    _LOADED = True


register_all()

__all__ = [
    "FeatureContext",
    "FeatureDefinition",
    "all_features",
    "enabled_features",
    "find_by_action",
    "get_feature",
    "handler_for",
    "register",
]
