from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.endpoints.telegram_support import (
    TelegramScope,
    _peek_pending_telegram_approval_for_tests,
    _reset_telegram_approval_state_for_tests,
    build_telegram_approval_callback_data,
)
from tldw_Server_API.app.services.mcp_hub_approval_service import _scope_key_for_tool_call


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    _reset_telegram_approval_state_for_tests()


def test_telegram_approval_callback_data_preserves_exact_scope_fingerprint() -> None:
    scope_key = _scope_key_for_tool_call("Bash", {"command": "git status", "args": ["--short"]})
    callback_data = build_telegram_approval_callback_data(
        approval_policy_id=17,
        context_key="user:202|group:88|persona:researcher",
        conversation_id="conv-1",
        tool_name="Bash",
        tool_args={"command": "git status", "args": ["--short"]},
        scope=TelegramScope(scope_type="group", scope_id=88),
        initiating_auth_user_id=202,
    )

    pending = _peek_pending_telegram_approval_for_tests(callback_data)

    assert pending is not None
    assert pending["scope_fingerprint"] == scope_key
    assert pending["tool_name"] == "Bash"
    assert pending["context_key"] == "user:202|group:88|persona:researcher"
    assert len(callback_data) <= 64


def test_telegram_approval_callback_data_changes_when_tool_scope_changes() -> None:
    first = build_telegram_approval_callback_data(
        approval_policy_id=17,
        context_key="user:202|group:88|persona:researcher",
        conversation_id="conv-1",
        tool_name="Bash",
        tool_args={"command": "git status"},
        scope=TelegramScope(scope_type="group", scope_id=88),
        initiating_auth_user_id=202,
    )
    second = build_telegram_approval_callback_data(
        approval_policy_id=17,
        context_key="user:202|group:88|persona:researcher",
        conversation_id="conv-1",
        tool_name="Bash",
        tool_args={"command": "git status --porcelain"},
        scope=TelegramScope(scope_type="group", scope_id=88),
        initiating_auth_user_id=202,
    )

    first_pending = _peek_pending_telegram_approval_for_tests(first)
    second_pending = _peek_pending_telegram_approval_for_tests(second)

    assert first_pending is not None
    assert second_pending is not None
    assert first_pending["scope_fingerprint"] != second_pending["scope_fingerprint"]
