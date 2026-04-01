from __future__ import annotations

"""Helpers for resolving companion storage IDs from logical user identities."""

import hmac

_COMPANION_STORAGE_ID_NAMESPACE = b"tldw-companion-storage-user-id"


def resolve_companion_storage_user_id(user_id: str | int) -> str:
    """Return the stable storage key used for companion personalization DB paths."""
    raw = str(user_id).strip()
    if not raw:
        raise ValueError("user_id must not be empty")
    try:
        return str(int(raw))
    except (TypeError, ValueError):
        digest = hmac.digest(
            _COMPANION_STORAGE_ID_NAMESPACE,
            raw.encode("utf-8"),
            "sha256",
        )
        return str(int.from_bytes(digest[:4], byteorder="big", signed=False))


__all__ = ["resolve_companion_storage_user_id"]
