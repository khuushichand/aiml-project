"""
Shared helpers for username validation and normalization.
"""

from __future__ import annotations

import re

_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
_RESERVED_USERNAMES = {"admin", "root", "system", "api", "null", "undefined"}


def normalize_admin_username(raw: str) -> str:
    candidate = (raw or "").strip().lower()
    if not candidate:
        raise ValueError("Username is required")
    if len(candidate) < 3:
        raise ValueError("Username must be at least 3 characters")
    if len(candidate) > 50:
        raise ValueError("Username must not exceed 50 characters")
    if not _USERNAME_PATTERN.match(candidate):
        raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
    if candidate in _RESERVED_USERNAMES:
        raise ValueError("This username is reserved and cannot be used")
    return candidate
