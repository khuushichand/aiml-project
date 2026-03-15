from __future__ import annotations

"""Feature flag helpers for runtime gating."""

import os

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.testing import is_truthy


def _flag_enabled(name: str, default: bool = True) -> bool:
    """Resolve a boolean flag from environment first, then runtime settings."""
    env_value = os.getenv(name)
    if env_value is None:
        env_value = os.getenv(name.lower())
    if env_value is not None:
        return is_truthy(env_value)

    try:
        raw = settings.get(name, None)
    except Exception:
        raw = None
    if raw is None:
        try:
            raw = settings.get(name.lower(), None)
        except Exception:
            raw = None

    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return is_truthy(str(raw))


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


def is_guardian_enabled() -> bool:
    try:
        return bool(settings.get("GUARDIAN_ENABLED", True))
    except Exception:
        return True


def is_self_monitoring_enabled() -> bool:
    try:
        return bool(settings.get("SELF_MONITORING_ENABLED", True))
    except Exception:
        return True


def is_collections_reading_saved_searches_enabled() -> bool:
    return _flag_enabled("COLLECTIONS_READING_SAVED_SEARCHES_ENABLED", default=True)


def is_collections_reading_note_links_enabled() -> bool:
    return _flag_enabled("COLLECTIONS_READING_NOTE_LINKS_ENABLED", default=True)


def is_collections_reading_archive_controls_enabled() -> bool:
    return _flag_enabled("COLLECTIONS_READING_ARCHIVE_CONTROLS_ENABLED", default=True)


def is_mcp_hub_policy_enforcement_enabled() -> bool:
    """Return True when MCP Hub runtime policy enforcement should be active."""
    return _flag_enabled("MCP_HUB_POLICY_ENFORCEMENT_ENABLED", default=True)
