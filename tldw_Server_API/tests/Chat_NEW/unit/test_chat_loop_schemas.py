"""Unit tests for chat loop API schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.chat_loop_schemas import (
    ChatLoopApprovalDecisionRequest,
    ChatLoopEvent,
    ChatLoopStartRequest,
)


@pytest.mark.unit
def test_chat_loop_event_accepts_valid_payload() -> None:
    event = ChatLoopEvent(
        run_id="run_1",
        seq=1,
        event="run_started",
        data={"conversation_id": "conv_1"},
    )
    assert event.run_id == "run_1"
    assert event.seq == 1
    assert event.event == "run_started"


@pytest.mark.unit
def test_chat_loop_event_rejects_non_positive_seq() -> None:
    with pytest.raises(ValidationError):
        ChatLoopEvent(
            run_id="run_1",
            seq=0,
            event="run_started",
            data={"conversation_id": "conv_1"},
        )


@pytest.mark.unit
def test_chat_loop_start_request_requires_messages() -> None:
    payload = ChatLoopStartRequest(messages=[{"role": "user", "content": "Hello"}])
    assert payload.messages[0]["role"] == "user"

    with pytest.raises(ValidationError):
        ChatLoopStartRequest(messages=[])


@pytest.mark.unit
def test_approval_decision_requires_non_empty_fields() -> None:
    payload = ChatLoopApprovalDecisionRequest(
        approval_id="approval_1",
        decision="approve",
    )
    assert payload.decision == "approve"

    with pytest.raises(ValidationError):
        ChatLoopApprovalDecisionRequest(approval_id="", decision="approve")
