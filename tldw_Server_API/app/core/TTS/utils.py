"""
Utility helpers for TTS modules.

Currently includes:
- parse_bool: robust conversion of common string/numeric values to boolean.
- estimate_max_new_tokens: heuristic sizing for TTS generation.
"""
from __future__ import annotations

from typing import Any

import math

TRUTHY_STRINGS = {"1", "true", "yes", "y", "on"}
FALSY_STRINGS = {"0", "false", "no", "n", "off", "none", "null", ""}


def parse_bool(value: Any, default: bool | None = False) -> bool:
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
        except (ValueError, TypeError, OverflowError):
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


def estimate_max_new_tokens(
    text: str,
    tokens_per_char: float = 2.5,
    safety: float = 1.3,
    min_tokens: int = 256,
    max_cap: int = 4096,
) -> int:
    """Estimate a safe max_new_tokens based on text length."""
    try:
        length = len(text or "")
    except Exception:
        length = 0
    try:
        est = math.ceil(length * float(tokens_per_char) * float(safety))
    except Exception:
        est = min_tokens
    try:
        min_tokens = int(min_tokens)
    except Exception:
        min_tokens = 0
    try:
        max_cap = int(max_cap)
    except Exception:
        max_cap = 4096
    if max_cap <= 0:
        max_cap = 4096
    if min_tokens < 0:
        min_tokens = 0
    return max(min_tokens, min(est, max_cap))
