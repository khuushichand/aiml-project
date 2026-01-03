"""
Security-related utilities for redacting secrets in logs.
"""

from __future__ import annotations


def redact_secret(value: str | None, head: int = 4, tail: int = 4) -> str:
    """Redact a secret string for logs.

    Returns "" for falsy input; masks short strings; keeps head/tail for long values.
    Example: redact_secret("abcdefghij", 4, 4) -> "abcd...ghij".
    """
    if head < 0 or tail < 0:
        raise ValueError("head and tail must be non-negative")
    if not value:
        return ""
    text = str(value)
    min_masked = max(len(text) // 3, 1)
    if len(text) <= head + tail or len(text) - head - tail < min_masked:
        return "*" * len(text)
    return f"{text[:head]}...{text[-tail:]}"
