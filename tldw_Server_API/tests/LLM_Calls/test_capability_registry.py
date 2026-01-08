from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError
from tldw_Server_API.app.core.LLM_Calls import capability_registry as cr


def test_normalize_payload_alias_does_not_override_canonical():
    payload = {"top_k": 9, "topk": 3}
    normalized = cr.normalize_payload("openrouter", payload)
    assert normalized["top_k"] == 9
    assert "topk" not in normalized


def test_normalize_payload_alias_fills_missing_canonical():
    payload = {"topk": 7}
    normalized = cr.normalize_payload("openrouter", payload)
    assert normalized["top_k"] == 7
    assert "topk" not in normalized


def test_validate_payload_rejects_unknown_fields():
    payload = {"messages": [], "model": "test", "unknown_field": 1}
    with pytest.raises(ChatBadRequestError) as exc:
        cr.validate_payload("openai", payload)
    assert "unknown_field" in str(exc.value)


def test_validate_payload_allows_provider_extensions():
    payload = {"messages": [], "model": "test", "top_k": 5, "min_p": 0.1}
    normalized = cr.validate_payload("openrouter", payload)
    assert normalized["top_k"] == 5
    assert normalized["min_p"] == 0.1


def test_validate_payload_rejects_extension_for_other_provider():
    payload = {"messages": [], "model": "test", "top_k": 5}
    with pytest.raises(ChatBadRequestError):
        cr.validate_payload("openai", payload)


def test_validate_payload_ignores_none_values():
    payload = {"messages": [], "model": "test", "unknown_field": None}
    normalized = cr.validate_payload("openai", payload)
    assert normalized["messages"] == []


def test_validate_payload_rejects_blocked_fields():
    payload = {"messages": [], "model": "test", "tool_choice": "auto"}
    with pytest.raises(ChatBadRequestError) as exc:
        cr.validate_payload("cohere", payload)
    assert "tool_choice" in str(exc.value)


def test_validate_payload_rejects_invalid_tools_shape():
    payload = {"messages": [], "model": "test", "tools": {"type": "function"}}
    with pytest.raises(ChatBadRequestError) as exc:
        cr.validate_payload("openai", payload)
    assert "tools" in str(exc.value).lower()


def test_validate_payload_rejects_tool_missing_name():
    payload = {
        "messages": [],
        "model": "test",
        "tools": [{"type": "function", "function": {"parameters": {}}}],
    }
    with pytest.raises(ChatBadRequestError) as exc:
        cr.validate_payload("openai", payload)
    assert "function.name" in str(exc.value)


def test_validate_payload_allows_valid_tool_definition():
    payload = {
        "messages": [],
        "model": "test",
        "tools": [{"type": "function", "function": {"name": "do", "parameters": {}}}],
    }
    normalized = cr.validate_payload("openai", payload)
    assert normalized["tools"][0]["function"]["name"] == "do"


def test_validate_payload_rejects_invalid_logit_bias():
    payload = {"messages": [], "model": "test", "logit_bias": {"not-a-token": 1}}
    with pytest.raises(ChatBadRequestError) as exc:
        cr.validate_payload("openai", payload)
    assert "logit_bias" in str(exc.value).lower()


def test_validate_payload_rejects_invalid_response_format():
    payload = {"messages": [], "model": "test", "response_format": {"type": "json_schema"}}
    with pytest.raises(ChatBadRequestError) as exc:
        cr.validate_payload("openai", payload)
    assert "response_format" in str(exc.value).lower()


def test_validate_payload_allows_unknown_response_format_type():
    payload = {"messages": [], "model": "test", "response_format": {"type": "custom"}}
    normalized = cr.validate_payload("openai", payload)
    assert normalized["response_format"]["type"] == "custom"


def test_validate_payload_allows_json_schema_response_format():
    payload = {
        "messages": [],
        "model": "test",
        "response_format": {"type": "json_schema", "json_schema": {"schema": {"type": "object"}}},
    }
    normalized = cr.validate_payload("openai", payload)
    assert normalized["response_format"]["type"] == "json_schema"


def test_validate_payload_allows_unknown_tool_type():
    payload = {"messages": [], "model": "test", "tools": [{"type": "custom_tool", "payload": {"ok": True}}]}
    normalized = cr.validate_payload("openai", payload)
    assert normalized["tools"][0]["type"] == "custom_tool"
