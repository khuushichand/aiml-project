# ruff: noqa: TRY003
"""
Shared helpers for username validation and normalization.
"""

from __future__ import annotations

import re

_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
_RESERVED_USERNAMES = {"admin", "root", "system", "api", "null", "undefined"}


class InvalidUsernameError(ValueError):
    """Raised when a username fails normalization or validation."""


def normalize_admin_username(raw: str) -> str:
    """
    Normalize and validate an admin username.

    Args:
        raw: Raw username input to normalize and validate.

    Returns:
        str: Normalized username (lowercased, trimmed).

    Raises:
        InvalidUsernameError: If the username is required but empty after trim.
        InvalidUsernameError: If the username is shorter than 3 characters.
        InvalidUsernameError: If the username exceeds 50 characters.
        InvalidUsernameError: If the username contains invalid characters
            (allowed: letters, numbers, underscores, hyphens).
        InvalidUsernameError: If the username is reserved (e.g., "admin", "root").

    Notes:
        Normalization/validation steps: trim whitespace, lowercase, enforce
        min/max length, match against the allowed pattern, and reject reserved
        usernames. There are no side effects; this is a pure helper. Allowed
        characters are ASCII letters, digits, underscores, and hyphens, and the
        length bounds are 3-50 characters.
    """
    candidate = (raw or "").strip().lower()
    if not candidate:
        raise InvalidUsernameError("Username is required")
    if len(candidate) < 3:
        raise InvalidUsernameError("Username must be at least 3 characters")
    if len(candidate) > 50:
        raise InvalidUsernameError("Username must not exceed 50 characters")
    if not _USERNAME_PATTERN.match(candidate):
        raise InvalidUsernameError("Username can only contain letters, numbers, underscores, and hyphens")
    if candidate in _RESERVED_USERNAMES:
        raise InvalidUsernameError("This username is reserved and cannot be used")
    return candidate
