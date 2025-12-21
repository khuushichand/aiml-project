from __future__ import annotations

from typing import Optional


def parse_boolean(val: Optional[str], default: bool = False) -> bool:
    """Parse a string-like value into a boolean.

    Treats '1', 'true', 'yes', and 'on' (case-insensitive, with surrounding
    whitespace ignored) as True. Returns ``default`` when ``val`` is None.
    """
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}
