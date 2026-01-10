from __future__ import annotations

import pytest

from tldw_Server_API.app.core.security_utils import redact_secret


@pytest.mark.unit
def test_redact_secret_empty():
     assert redact_secret("") == ""


@pytest.mark.unit
def test_redact_secret_none():
     assert redact_secret(None) == ""


@pytest.mark.unit
def test_redact_secret_short_masks_all():
     assert redact_secret("abcd") == "****"
    assert redact_secret("abcdefgh") == "********"


@pytest.mark.unit
def test_redact_secret_long_keeps_head_tail():
     assert redact_secret("abcdefghij") == "abcd...ghij"


@pytest.mark.unit
def test_redact_secret_non_ascii():
     value = "秘密情報12345"
    assert redact_secret(value, head=2, tail=2) == f"{value[:2]}...{value[-2:]}"
