from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from loguru import logger


COMPAT_PATHS: dict[str, dict[str, Any]] = {
    "web_scraping_legacy_fallback": {
        "source": "tldw_Server_API.app.services.web_scraping_service",
        "sunset": "2026-06-30",
        "successor": "enhanced_web_scraping_service",
    },
    "llm_chat_legacy_session": {
        "source": "tldw_Server_API.app.core.LLM_Calls.chat_calls",
        "sunset": "2026-07-15",
        "successor": "http_client.fetch streaming + provider adapters",
    },
    "auth_db_execute_compat": {
        "source": "tldw_Server_API.app.services.auth_service",
        "sunset": "2026-08-01",
        "successor": "backend-specific auth db adapters",
    },
}

_WARNED_THIS_CYCLE: ContextVar[frozenset[str]] = ContextVar(
    "runtime_deprecation_warned_keys",
    default=frozenset(),
)


def load_compat_registry() -> dict[str, dict[str, Any]]:
    return dict(COMPAT_PATHS)


def reset_runtime_deprecation_cycle() -> None:
    _WARNED_THIS_CYCLE.set(frozenset())


def _mark_deprecation_emitted(key: str) -> bool:
    seen = _WARNED_THIS_CYCLE.get()
    if key in seen:
        return False
    _WARNED_THIS_CYCLE.set(seen.union({key}))
    return True


def _compose_runtime_deprecation_message(
    key: str,
    entry: dict[str, Any] | None,
    *,
    message: str | None = None,
) -> str:
    if entry is None:
        return message or (
            f"Runtime compatibility path '{key}' executed without a registry entry. "
            "Register a sunset date and successor."
        )

    sunset = str(entry.get("sunset", "unspecified"))
    source = str(entry.get("source", "unspecified"))
    successor = str(entry.get("successor", "unspecified"))

    if message:
        return (
            f"{message} "
            f"[compat_key={key} sunset={sunset} successor={successor} source={source}]"
        )

    return (
        f"Runtime compatibility path '{key}' executed. "
        f"sunset={sunset}, successor={successor}, source={source}."
    )


def log_runtime_deprecation(key: str, *, message: str | None = None) -> None:
    if not _mark_deprecation_emitted(key):
        return

    entry = COMPAT_PATHS.get(key)
    logger.warning(_compose_runtime_deprecation_message(key, entry, message=message))
