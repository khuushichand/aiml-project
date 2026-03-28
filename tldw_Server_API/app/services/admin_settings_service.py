from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    AdminCleanupSettingsUpdate,
    NotesTitleSettingsUpdate,
)
from tldw_Server_API.app.core.config import settings as app_settings


async def get_cleanup_settings() -> dict[str, Any]:
    """Get cleanup worker settings (enabled, interval in seconds)."""
    try:
        enabled = bool(app_settings.get("EPHEMERAL_CLEANUP_ENABLED", True))
        interval = int(app_settings.get("EPHEMERAL_CLEANUP_INTERVAL_SEC", 1800))
        return {"enabled": enabled, "interval_sec": interval}
    except Exception as exc:
        logger.error(f"Failed to get cleanup settings: {exc}")
        raise HTTPException(status_code=500, detail="Failed to get cleanup settings") from exc


async def set_cleanup_settings(payload: AdminCleanupSettingsUpdate) -> dict[str, Any]:
    """Set cleanup worker settings (enabled, interval_sec)."""
    try:
        if payload.enabled is not None:
            app_settings["EPHEMERAL_CLEANUP_ENABLED"] = bool(payload.enabled)
        if payload.interval_sec is not None:
            app_settings["EPHEMERAL_CLEANUP_INTERVAL_SEC"] = int(payload.interval_sec)
        enabled = bool(app_settings.get("EPHEMERAL_CLEANUP_ENABLED", True))
        interval = int(app_settings.get("EPHEMERAL_CLEANUP_INTERVAL_SEC", 1800))
        return {"enabled": enabled, "interval_sec": interval}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to set cleanup settings: {exc}")
        raise HTTPException(status_code=500, detail="Failed to set cleanup settings") from exc


async def get_notes_title_settings() -> dict[str, Any]:
    """Get Notes auto-title settings (LLM enabled flag and default strategy)."""
    try:
        llm_enabled = bool(app_settings.get("NOTES_TITLE_LLM_ENABLED", False))
        default_strategy = str(app_settings.get("NOTES_TITLE_DEFAULT_STRATEGY", "heuristic")).lower()
        effective_strategy = (
            default_strategy if llm_enabled or default_strategy == "heuristic" else "heuristic"
        )
        return {
            "llm_enabled": llm_enabled,
            "default_strategy": default_strategy,
            "effective_strategy": effective_strategy,
            "strategies": ["heuristic", "llm", "llm_fallback"],
        }
    except Exception as exc:
        logger.error(f"Failed to get notes title settings: {exc}")
        raise HTTPException(status_code=500, detail="Failed to get notes title settings") from exc


async def set_notes_title_settings(payload: NotesTitleSettingsUpdate) -> dict[str, Any]:
    """Update Notes auto-title settings."""
    try:
        if payload.llm_enabled is not None:
            app_settings["NOTES_TITLE_LLM_ENABLED"] = bool(payload.llm_enabled)
        if payload.default_strategy is not None:
            app_settings["NOTES_TITLE_DEFAULT_STRATEGY"] = payload.default_strategy
        llm_enabled = bool(app_settings.get("NOTES_TITLE_LLM_ENABLED", False))
        default_strategy = str(app_settings.get("NOTES_TITLE_DEFAULT_STRATEGY", "heuristic")).lower()
        effective_strategy = (
            default_strategy if llm_enabled or default_strategy == "heuristic" else "heuristic"
        )
        return {
            "llm_enabled": llm_enabled,
            "default_strategy": default_strategy,
            "effective_strategy": effective_strategy,
            "strategies": ["heuristic", "llm", "llm_fallback"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to set notes title settings: {exc}")
        raise HTTPException(status_code=500, detail="Failed to set notes title settings") from exc


# ---------------------------------------------------------------------------
# Security Risk Weights
# ---------------------------------------------------------------------------

_DEFAULT_RISK_WEIGHTS: dict[str, Any] = {
    "mfa_adoption": {"weight": 3, "cap": 40},
    "api_key_age": {"weight": 2, "cap": 25},
    "failed_logins": {"weight": 1, "cap": 20},
    "suspicious_activity": {"weight": 4, "cap": 20},
}

# In-memory store — persisted across requests within a single process
_risk_weights: dict[str, Any] | None = None


async def get_risk_weights() -> dict[str, Any]:
    """Return the current risk weight configuration."""
    global _risk_weights
    if _risk_weights is None:
        _risk_weights = dict(_DEFAULT_RISK_WEIGHTS)
    return {"weights": _risk_weights}


async def set_risk_weights(weights: dict[str, Any]) -> dict[str, Any]:
    """Update risk weight configuration."""
    global _risk_weights
    # Validate structure
    validated: dict[str, Any] = {}
    for key in _DEFAULT_RISK_WEIGHTS:
        if key in weights and isinstance(weights[key], dict):
            w = max(0, min(10, int(weights[key].get("weight", _DEFAULT_RISK_WEIGHTS[key]["weight"]))))
            c = max(0, min(100, int(weights[key].get("cap", _DEFAULT_RISK_WEIGHTS[key]["cap"]))))
            validated[key] = {"weight": w, "cap": c}
        else:
            validated[key] = dict(_DEFAULT_RISK_WEIGHTS[key])
    _risk_weights = validated
    return {"weights": _risk_weights}
