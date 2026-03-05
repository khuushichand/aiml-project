"""Unit tests for chat loop mode detection and gating helpers."""

from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Chat.chat_loop_engine import is_chat_loop_mode_enabled


@pytest.mark.unit
@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({}, False),
        ({"chat_loop_mode": "legacy"}, False),
        ({"chat_loop_mode": "enabled"}, True),
        ({"chat_loop_mode": "ENABLED"}, True),
        ({"chat_loop_mode": True}, True),
        ({"chat_loop_mode": False}, False),
        ({"chat_loop_mode": "0"}, False),
        ({"chat_loop_mode": "1"}, True),
    ],
)
def test_is_chat_loop_mode_enabled(payload: dict[str, object], expected: bool) -> None:
    assert is_chat_loop_mode_enabled(payload) is expected
