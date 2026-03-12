from __future__ import annotations

"""Deterministic proactive delivery policy helpers for companion reflections."""

from typing import Any


def _normalize_theme_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric != numeric:  # NaN guard
        return default
    return numeric


def classify_companion_reflection_delivery(
    *,
    cadence: str,
    activity_count: int,
    theme_key: str,
    signal_strength: float,
    recent_reflections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Classify whether a reflection should be delivered, downgraded, or suppressed."""
    normalized_theme = _normalize_theme_key(theme_key)
    normalized_cadence = str(cadence or "").strip().lower() or "daily"
    current_signal = _coerce_float(signal_strength)
    recent = list(recent_reflections or [])

    for reflection in recent:
        if _normalize_theme_key(reflection.get("theme_key")) != normalized_theme:
            continue
        if str(reflection.get("delivery_decision") or "").strip().lower() != "delivered":
            continue
        reflection_cadence = str(reflection.get("cadence") or normalized_cadence).strip().lower()
        if normalized_cadence and reflection_cadence != normalized_cadence:
            continue
        prior_signal = _coerce_float(reflection.get("signal_strength"))
        if current_signal - prior_signal < 1.5:
            return {
                "delivery_decision": "suppressed",
                "delivery_reason": "duplicate_weak_delta",
            }
        break

    if int(activity_count) < 2 or current_signal < 2.0:
        return {
            "delivery_decision": "suppressed",
            "delivery_reason": "low_signal",
        }

    return {
        "delivery_decision": "delivered",
        "delivery_reason": "meaningful_signal",
    }


__all__ = ["classify_companion_reflection_delivery"]
