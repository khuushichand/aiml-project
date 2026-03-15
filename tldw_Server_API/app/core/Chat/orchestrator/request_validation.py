"""Request normalization helpers for chat orchestration."""

from __future__ import annotations

from typing import Any


def normalize_selected_parts(selected_parts: Any) -> list[str]:
    """Normalize selected_parts input to a clean list of strings."""
    if isinstance(selected_parts, (list, tuple)):
        return [str(part) for part in selected_parts if part]
    if selected_parts:
        return [str(selected_parts)]
    return []


def normalize_temperature(temperature: Any, default: float = 0.7) -> float:
    """Normalize temperature input to a float with safe fallback."""
    try:
        return float(temperature) if temperature is not None else default
    except (TypeError, ValueError):
        return default
