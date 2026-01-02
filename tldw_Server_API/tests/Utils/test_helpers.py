from __future__ import annotations

from typing import Optional


def redact_secret(value: Optional[str], head: int = 4, tail: int = 4) -> str:
    """Redact a secret string (Optional[str], int, int -> str) for logs.
    Returns "" for falsy input; masks short strings; keeps head/tail for long values.
    Example: redact_secret("abcdefghij", 4, 4) -> "abcd...ghij".
    """
    if not value:
        return ""
    text = str(value)
    if len(text) <= head + tail:
        return "*" * len(text)
    return f"{text[:head]}...{text[-tail:]}"


def test_redact_secret_empty_and_none():
    assert redact_secret("") == ""
    assert redact_secret(None) == ""


def test_redact_secret_short_masks_all():
    assert redact_secret("abcd") == "****"
    assert redact_secret("abcdefgh") == "********"


def test_redact_secret_long_keeps_head_tail():
    assert redact_secret("abcdefghij") == "abcd...ghij"


def test_redact_secret_non_ascii():
    value = "秘密情報12345"
    assert redact_secret(value, head=2, tail=2) == f"{value[:2]}...{value[-2:]}"
