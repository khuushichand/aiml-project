"""Tests for guided tool-choice normalization when no executable tools exist."""

from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import ChatCompletionRequest
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload


@pytest.mark.unit
def test_auto_tool_choice_with_empty_toolset_is_normalized_safely() -> None:
    payload = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "test",
        "tool_choice": "auto",
        "tools": [],
    }
    normalized = validate_payload("openai", payload)
    assert normalized.get("tools") in (None, [])
    assert normalized.get("tool_choice") in (None, "none")


@pytest.mark.unit
def test_required_tool_choice_with_empty_toolset_still_rejected() -> None:
    payload = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "test",
        "tool_choice": "required",
        "tools": [],
    }
    with pytest.raises(ChatBadRequestError):
        validate_payload("openai", payload)


@pytest.mark.unit
def test_chat_request_schema_normalizes_auto_choice_for_empty_tools() -> None:
    request = ChatCompletionRequest(
        messages=[{"role": "user", "content": "hello"}],
        model="gpt-4o-mini",
        tool_choice="auto",
        tools=[],
    )
    assert request.tool_choice in (None, "none")
    assert request.tools in (None, [])
