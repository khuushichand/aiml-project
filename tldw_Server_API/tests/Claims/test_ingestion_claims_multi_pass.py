import pytest

from tldw_Server_API.app.core.Claims_Extraction.ingestion_claims import extract_claims_for_chunks
from tldw_Server_API.app.core.config import settings


@pytest.mark.unit
def test_ingestion_multi_pass_dedupes_repeated_claims(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.ingestion_claims as ingestion_mod

    calls = {"count": 0}

    def _fake_chat_api_call(*args, **kwargs):
        calls["count"] += 1
        return '{"claims": [{"text": "Repeated ingestion claim."}]}'

    monkeypatch.setitem(settings, "CLAIMS_EXTRACTION_PASSES", 3)
    monkeypatch.setitem(settings, "CLAIMS_CONTEXT_WINDOW_CHARS", 0)
    monkeypatch.setattr(ingestion_mod, "chat_api_call", _fake_chat_api_call, raising=False)

    claims = extract_claims_for_chunks(
        [{"text": "Repeated ingestion claim.", "metadata": {"chunk_index": 0}}],
        extractor_mode="openai",
        max_per_chunk=3,
    )

    assert calls["count"] == 3
    assert len(claims) == 1
    assert claims[0]["claim_text"] == "Repeated ingestion claim."


@pytest.mark.unit
def test_ingestion_context_window_includes_previous_chunk_tail(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.ingestion_claims as ingestion_mod

    observed_prompts: list[str] = []

    def _fake_chat_api_call(
        api_endpoint,
        messages_payload,
        api_key=None,
        temp=None,
        system_message=None,
        streaming=False,
        model=None,
        response_format=None,
        **kwargs,
    ):
        observed_prompts.append(str(messages_payload[0].get("content") if messages_payload else ""))
        return '{"claims": [{"text": "Context claim."}]}'

    def _fake_load_prompt(_module: str, key: str):
        if key == "claims_extractor_prompt":
            return "Extract up to {max_claims} claims.\\nANSWER:\\n{answer}"
        return None

    monkeypatch.setitem(settings, "CLAIMS_EXTRACTION_PASSES", 1)
    monkeypatch.setitem(settings, "CLAIMS_CONTEXT_WINDOW_CHARS", 12)
    monkeypatch.setattr(ingestion_mod, "chat_api_call", _fake_chat_api_call, raising=False)
    monkeypatch.setattr(ingestion_mod, "load_prompt", _fake_load_prompt)

    chunks = [
        {"text": "Chunk one introduces Alice and key details.", "metadata": {"chunk_index": 0}},
        {"text": "She later confirms the result in the second chunk.", "metadata": {"chunk_index": 1}},
    ]

    claims = extract_claims_for_chunks(chunks, extractor_mode="openai", max_per_chunk=1)

    assert claims
    assert len(observed_prompts) == 2
    first_tail = chunks[0]["text"][-12:]
    assert first_tail in observed_prompts[1]
