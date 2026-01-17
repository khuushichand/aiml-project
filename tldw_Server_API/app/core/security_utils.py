"""
Security-related utilities for redacting secrets in logs.
"""

from __future__ import annotations

from tldw_Server_API.app.core.exceptions import InvalidSecretRedactionParametersError


def redact_secret(value: str | None, head: int = 4, tail: int = 4) -> str:
    """Redact a secret string for logs.

    Returns "" for falsy input; masks short strings; keeps head/tail for long values
    while ensuring at least one-third remains redacted.
    Example: redact_secret("abcdefghijkl", 4, 4) -> "abcd...ijkl".
    """
    if head < 0 or tail < 0:
        raise InvalidSecretRedactionParametersError()
    if not value:
        return ""
    text = str(value)
    min_masked = max(len(text) // 3, 1)
    if len(text) <= head + tail or len(text) - head - tail < min_masked:
        return "*" * len(text)
    return f"{text[:head]}...{text[-tail:]}"
