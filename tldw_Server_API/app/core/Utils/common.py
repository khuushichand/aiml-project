from __future__ import annotations

from tldw_Server_API.app.core.testing import is_truthy


def parse_boolean(val: str | None, default: bool = False) -> bool:
    """Parse a string-like value into a boolean.

    Treats '1', 'true', 'yes', 'y', and 'on' (case-insensitive, with surrounding
    whitespace ignored) as True. Returns ``default`` when ``val`` is None.
    """
    if val is None:
        return default
    return is_truthy(val)
