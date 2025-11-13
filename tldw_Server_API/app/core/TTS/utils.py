"""
Utility helpers for TTS modules.

Currently includes:
- parse_bool: robust conversion of common string/numeric values to boolean.
"""
from __future__ import annotations

from typing import Any, Optional


TRUTHY_STRINGS = {"1", "true", "yes", "y", "on"}
FALSY_STRINGS = {"0", "false", "no", "n", "off", "none", "null", ""}


def parse_bool(value: Any, default: Optional[bool] = False) -> bool:
    """Parse a value into a boolean in a tolerant, explicit way.

    Behavior:
    - bool -> returned as-is
    - int/float -> 0 is False, non-zero True
    - str -> case-insensitive check against common truthy/falsy tokens;
             unknown strings return `default`
    - None -> returns `default` (defaults to False)
    - other types -> bool(value) if default is None else default
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default) if default is not None else False
    if isinstance(value, (int, float)):
        try:
            return int(value) != 0
        except Exception:
            return bool(default) if default is not None else False
    if isinstance(value, str):
        s = value.strip().lower()
        if s in TRUTHY_STRINGS:
            return True
        if s in FALSY_STRINGS:
            return False
        # Unknown string token
        return bool(default) if default is not None else False
    # Fallback for other types
    return bool(value) if default is None else bool(default)

