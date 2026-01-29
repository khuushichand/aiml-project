from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import (
    ChatCompletionRequest,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from tldw_Server_API.app.core.Chat.chat_service import apply_prompt_templating


def _extract_text_content(message):
    content = message.get("content")
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if part.get("type") == "text")
    return content


def test_apply_prompt_templating_strips_system_messages():
    request_data = ChatCompletionRequest(
        model="test-model",
        messages=[
            ChatCompletionSystemMessageParam(role="system", content="You are a helpful assistant."),
            ChatCompletionUserMessageParam(role="user", content="Hello there."),
        ],
    )
    llm_payload_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello there."},
    ]
    character_card = {"name": "Test", "system_prompt": "Default prompt"}

    final_system_message, payload = apply_prompt_templating(
        request_data=request_data,
        character_card=character_card,
        llm_payload_messages=llm_payload_messages,
    )

    assert final_system_message == "You are a helpful assistant."
    assert all(msg.get("role") != "system" for msg in payload)
    assert len(payload) == 1
    assert payload[0]["role"] == "user"
    assert _extract_text_content(payload[0]) == "Hello there."


def test_apply_prompt_templating_uses_payload_system_message():
    request_data = ChatCompletionRequest(
        model="test-model",
        messages=[ChatCompletionUserMessageParam(role="user", content="Hello there.")],
    )
    llm_payload_messages = [
        {"role": "system", "content": "Persisted system prompt"},
        {"role": "user", "content": "Hello there."},
    ]
    character_card = {"name": "Test", "system_prompt": "Default prompt"}

    final_system_message, payload = apply_prompt_templating(
        request_data=request_data,
        character_card=character_card,
        llm_payload_messages=llm_payload_messages,
    )

    assert final_system_message == "Persisted system prompt"
    assert all(msg.get("role") != "system" for msg in payload)
    assert len(payload) == 1
    assert payload[0]["role"] == "user"
    assert _extract_text_content(payload[0]) == "Hello there."


def test_apply_prompt_templating_combines_request_system_messages():
    request_data = ChatCompletionRequest(
        model="test-model",
        messages=[
            ChatCompletionSystemMessageParam(role="system", content="Primary system."),
            ChatCompletionSystemMessageParam(role="system", content="Injected system."),
            ChatCompletionUserMessageParam(role="user", content="Hello there."),
        ],
    )
    llm_payload_messages = [
        {"role": "system", "content": "Primary system."},
        {"role": "system", "content": "Injected system."},
        {"role": "user", "content": "Hello there."},
    ]
    character_card = {"name": "Test", "system_prompt": "Default prompt"}

    final_system_message, payload = apply_prompt_templating(
        request_data=request_data,
        character_card=character_card,
        llm_payload_messages=llm_payload_messages,
    )

    assert final_system_message == "Primary system.\n\nInjected system."
    assert all(msg.get("role") != "system" for msg in payload)
    assert len(payload) == 1
    assert payload[0]["role"] == "user"
