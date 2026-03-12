from __future__ import annotations

"""Helpers for resolving companion storage IDs from logical user identities."""

import hashlib


def resolve_companion_storage_user_id(user_id: str | int) -> str:
    """Return the stable storage key used for companion personalization DB paths."""
    raw = str(user_id).strip()
    if not raw:
        raise ValueError("user_id must not be empty")
    try:
        return str(int(raw))
    except (TypeError, ValueError):
        try:
            digest = hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).digest()
        except TypeError:  # pragma: no cover - compatibility fallback
            digest = hashlib.sha1(raw.encode("utf-8")).digest()  # nosec B324
        return str(int.from_bytes(digest[:4], byteorder="big", signed=False))


__all__ = ["resolve_companion_storage_user_id"]
