"""
Security-related utilities for redacting secrets in logs.
"""

from __future__ import annotations


def redact_secret(value: str | None, head: int = 4, tail: int = 4) -> str:
    """Redact a secret string for logs.

    Returns "" for falsy input; masks short strings; keeps head/tail for long values.
    Example: redact_secret("abcdefghij", 4, 4) -> "abcd...ghij".
    """
    if not value:
        return ""
    text = str(value)
    if len(text) <= head + tail:
        return "*" * len(text)
    return f"{text[:head]}...{text[-tail:]}"
