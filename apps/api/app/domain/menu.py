"""Employer menu construction, driven by the feature registry and project flags."""

from __future__ import annotations

from app.adapters.telegram.formatting import inline_keyboard
from app.domain.features import FEATURES, enabled_features


def project_menu_buttons(project_index: int, flags: dict[str, bool]) -> dict:
    """Build the inline keyboard for one project.

    Callback data stays short and contains no ids, license codes or amounts:
    ``<project index>:<action>``. The index is resolved against a fresh database
    lookup on every callback, so it cannot be replayed across users.
    """
    buttons: list[list[tuple[str, str]]] = []
    row: list[tuple[str, str]] = []
    for definition in enabled_features(flags):
        if definition.implemented and definition.action:
            callback = f"{project_index}:{definition.action}"
        else:
            callback = f"{project_index}:soon:{definition.key}"
        row.append((definition.label, callback))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([("دریافت مجدد منو", "h")])
    return inline_keyboard(buttons)


def project_picker_buttons(projects: list[tuple[str, int]]) -> dict:
    rows = [[(name, f"p:{index}")] for name, index in projects]
    rows.append([("راهنما", "help")])
    return inline_keyboard(rows)


def soon_key_for_callback(callback: str) -> str | None:
    """Extract the registry key for ``<n>:soon:<key>`` callbacks."""
    parts = callback.split(":")
    if len(parts) == 3 and parts[1] == "soon" and parts[2] in FEATURES:
        return parts[2]
    return None
