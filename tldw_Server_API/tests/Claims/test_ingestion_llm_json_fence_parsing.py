import json

from tldw_Server_API.app.core.Ingestion_Media_Processing.Claims.ingestion_claims import extract_claims_for_chunks


def test_ingestion_llm_extractor_parses_json_in_fenced_block(monkeypatch):
    # Simulate provider returning JSON inside triple backticks
    def _fake_chat_api_call(api_endpoint, messages_payload, api_key=None, temp=None, system_message=None, streaming=False, model=None):
        payload = {"claims": [{"text": "Claim A."}, {"text": "Claim B."}]}
        return f"Here are claims:\n```json\n{json.dumps(payload)}\n```\nThanks."

    # Patch the module-level override consumed by ingestion_claims
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Claims.ingestion_claims as mod
    monkeypatch.setattr(mod, "chat_api_call", _fake_chat_api_call, raising=False)

    chunks = [{"text": "irrelevant", "metadata": {"chunk_index": 0}}]
    # Force LLM path by specifying a known provider name
    claims = extract_claims_for_chunks(chunks, extractor_mode="openai", max_per_chunk=5)
    texts = [c.get("claim_text", "") for c in claims]
    assert "Claim A." in texts and "Claim B." in texts
