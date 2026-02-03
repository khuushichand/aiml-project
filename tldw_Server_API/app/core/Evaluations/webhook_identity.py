"""Webhook identity helpers for Evaluations.

Keeps webhook ownership consistent with user_{id} while tolerating
legacy identifiers in tests or internal call sites.
"""

from __future__ import annotations

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


def _strip_user_prefix(value: str) -> str:
    if value.startswith("user_"):
        return value[5:]
    return value


def webhook_user_id_from_user(user: User, *, fallback: str = "1") -> str:
    """Return a webhook user id in the form user_{id}.

    Prefers numeric IDs when available; preserves existing user_ prefix when present.
    """
    raw = None
    try:
        raw = user.id_int
    except Exception:
        raw = None

    if raw is None:
        try:
            raw = _strip_user_prefix(user.id_str)
        except Exception:
            raw = None

    raw_str = str(raw or "").strip()
    if not raw_str:
        raw_str = str(fallback)

    if raw_str.startswith("user_"):
        return raw_str
    return f"user_{raw_str}"


def webhook_user_id_from_value(value: str | None) -> str | None:
    """Normalize a stored or provided user id to a webhook user id.

    Keeps non-numeric identifiers (e.g. test_user) intact.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.startswith("user_"):
        return raw
    if raw.isdigit():
        return f"user_{raw}"
    return raw
