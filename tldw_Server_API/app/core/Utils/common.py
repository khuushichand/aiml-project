from __future__ import annotations


def parse_boolean(val: str | None, default: bool = False) -> bool:
    """Parse a string-like value into a boolean.

    Treats '1', 'true', 'yes', and 'on' (case-insensitive, with surrounding
    whitespace ignored) as True. Returns ``default`` when ``val`` is None.
    """
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}
