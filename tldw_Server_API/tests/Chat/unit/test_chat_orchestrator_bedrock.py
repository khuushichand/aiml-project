import os
import pytest


pytestmark = pytest.mark.unit


def test_orchestrator_maps_bedrock_extras(monkeypatch):
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call

    captured = {}

    def fake_dispatch(**kwargs):
        # Capture kwargs for assertions
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Chat.chat_orchestrator.perform_chat_api_call",
        fake_dispatch,
    )

    # Prepare extras that should be forwarded
    extra_headers = {
        'X-Amzn-Bedrock-GuardrailIdentifier': 'gr-123',
        'X-Amzn-Bedrock-GuardrailVersion': '1',
        'X-Amzn-Bedrock-Trace': 'ENABLED',
    }
    extra_body = {
        'amazon-bedrock-guardrailConfig': {'tagSuffix': 'team-a'}
    }

    # Call orchestrator
    resp = chat_api_call(
        api_endpoint='bedrock',
        messages_payload=[{"role": "user", "content": "hello"}],
        api_key='test-key',
        model='test-model',
        extra_headers=extra_headers,
        extra_body=extra_body,
    )

    # Verify our fake was called and extras were forwarded
    assert resp == {"ok": True}
    assert captured.get("api_endpoint") == "bedrock"
    assert captured.get("messages_payload") == [{"role": "user", "content": "hello"}]
    assert captured.get('extra_headers') == extra_headers
    assert captured.get('extra_body') == extra_body
