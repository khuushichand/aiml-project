import os
import pytest


pytestmark = pytest.mark.unit


def test_orchestrator_maps_bedrock_extras(monkeypatch):
    from tldw_Server_API.app.core.Chat import provider_config as pc
    from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call

    captured = {}

    def fake_bedrock_handler(**kwargs):
        # Capture kwargs for assertions
        captured.update(kwargs)
        return {"ok": True}

    # Patch the handler mapping to our fake
    monkeypatch.setitem(pc.API_CALL_HANDLERS, 'bedrock', fake_bedrock_handler)

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

    # Verify our fake was called and extras were mapped through
    assert resp == {"ok": True}
    # bedrock maps messages_payload -> input_data; extras should pass through as-is
    assert 'input_data' in captured
    assert captured.get('extra_headers') == extra_headers
    assert captured.get('extra_body') == extra_body
