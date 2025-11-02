from __future__ import annotations

"""Feature flag helpers for runtime gating."""

from tldw_Server_API.app.core.config import settings


def is_personalization_enabled() -> bool:
    try:
        return bool(settings.get("PERSONALIZATION_ENABLED", True))
    except Exception:
        return True


def is_persona_enabled() -> bool:
    try:
        return bool(settings.get("PERSONA_ENABLED", True))
    except Exception:
        return True
