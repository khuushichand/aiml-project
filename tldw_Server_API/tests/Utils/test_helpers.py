from __future__ import annotations

from tldw_Server_API.app.core.security_utils import redact_secret


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
