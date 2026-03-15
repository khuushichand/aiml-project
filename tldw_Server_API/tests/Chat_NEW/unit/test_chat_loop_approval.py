"""Unit tests for chat-loop approval token mint/verify."""

from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Chat.chat_loop_approval import (
    InMemoryApprovalNonceStore,
    mint_approval_token,
    verify_approval_token,
)


@pytest.mark.unit
def test_approval_token_rejects_mismatched_args_hash() -> None:
    token = mint_approval_token(
        run_id="run_1",
        seq=7,
        tool_call_id="tc_1",
        args_hash="hash_a",
        secret="test-secret",
    )

    ok, error = verify_approval_token(
        token=token,
        run_id="run_1",
        seq=7,
        tool_call_id="tc_1",
        args_hash="hash_b",
        secret="test-secret",
    )

    assert ok is False
    assert error is not None
    assert "args_hash" in error


@pytest.mark.unit
def test_approval_token_is_single_use_when_nonce_store_present() -> None:
    store = InMemoryApprovalNonceStore()
    token = mint_approval_token(
        run_id="run_1",
        seq=8,
        tool_call_id="tc_2",
        args_hash="hash_x",
        secret="test-secret",
    )

    first_ok, _ = verify_approval_token(
        token=token,
        run_id="run_1",
        seq=8,
        tool_call_id="tc_2",
        args_hash="hash_x",
        secret="test-secret",
        nonce_store=store,
    )
    second_ok, second_error = verify_approval_token(
        token=token,
        run_id="run_1",
        seq=8,
        tool_call_id="tc_2",
        args_hash="hash_x",
        secret="test-secret",
        nonce_store=store,
    )

    assert first_ok is True
    assert second_ok is False
    assert second_error is not None
    assert "already used" in second_error
