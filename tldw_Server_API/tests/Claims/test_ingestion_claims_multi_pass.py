from typing import Any

import pytest

from tldw_Server_API.app.core.Claims_Extraction.ingestion_claims import extract_claims_for_chunks
from tldw_Server_API.app.core.config import settings


@pytest.mark.unit
def test_ingestion_multi_pass_dedupes_repeated_claims(monkeypatch):
    import tldw_Server_API.app.core.Claims_Extraction.ingestion_claims as ingestion_mod

    calls = {"count": 0}

    def _fake_chat_api_call(
        api_endpoint: str,
        messages_payload: list[dict[str, Any]],
        api_key: str | None = None,
        temp: float | None = None,
        system_message: str | None = None,
        *,
        streaming: bool = False,
        model: str | None = None,
        response_format: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Return a deterministic repeated-claim JSON payload for each call."""
        _ = (
            api_endpoint,
            messages_payload,
            api_key,
            temp,
            system_message,
            streaming,
            model,
            response_format,
            kwargs,
        )
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
        api_endpoint: str,
        messages_payload: list[dict[str, Any]],
        api_key: str | None = None,
        temp: float | None = None,
        system_message: str | None = None,
        *,
        streaming: bool = False,
        model: str | None = None,
        response_format: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Capture prompt text and return chunk-specific claims as JSON."""
        _ = (
            api_endpoint,
            api_key,
            temp,
            system_message,
            streaming,
            model,
            response_format,
            kwargs,
        )
        prompt = str(messages_payload[0].get("content") if messages_payload else "")
        observed_prompts.append(prompt)
        if "second chunk" in prompt:
            return '{"claims": [{"text": "She later confirms the result in the second chunk."}]}'
        return '{"claims": [{"text": "Chunk one introduces Alice and key details."}]}'

    def _fake_load_prompt(_module: str, key: str) -> str | None:
        """Return a context-aware test prompt template for claims extraction."""
        if key == "claims_extractor_prompt":
            return (
                "Extract up to {max_claims} claims.\\n"
                "CONTEXT (do not extract claims from this):\\n{context}\\n\\n"
                "CHUNK (extract claims only from this):\\n{chunk}"
            )
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
    assert "CONTEXT (do not extract claims from this):" in observed_prompts[1]
    assert "CHUNK (extract claims only from this):" in observed_prompts[1]
    assert first_tail in observed_prompts[1]
    assert chunks[1]["text"] in observed_prompts[1]
    assert "{context}" not in observed_prompts[1]
    assert "{chunk}" not in observed_prompts[1]


@pytest.mark.unit
def test_ingestion_context_window_skips_unaligned_claims_and_alignment_events(
    monkeypatch,
):
    import tldw_Server_API.app.core.Claims_Extraction.ingestion_claims as ingestion_mod

    alignment_events: list[dict[str, object]] = []

    def _fake_chat_api_call(
        api_endpoint: str,
        messages_payload: list[dict[str, Any]],
        api_key: str | None = None,
        temp: float | None = None,
        system_message: str | None = None,
        *,
        streaming: bool = False,
        model: str | None = None,
        response_format: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Return a non-aligning claim payload used to test skip behavior."""
        _ = (
            api_endpoint,
            messages_payload,
            api_key,
            temp,
            system_message,
            streaming,
            model,
            response_format,
            kwargs,
        )
        return '{"claims": [{"text": "Claim that does not exist in either chunk."}]}'

    def _record_alignment_event(**kwargs: object) -> None:
        """Collect alignment event payloads emitted during extraction."""
        alignment_events.append(kwargs)

    monkeypatch.setitem(settings, "CLAIMS_EXTRACTION_PASSES", 1)
    monkeypatch.setitem(settings, "CLAIMS_CONTEXT_WINDOW_CHARS", 16)
    monkeypatch.setattr(ingestion_mod, "chat_api_call", _fake_chat_api_call, raising=False)
    monkeypatch.setattr(
        ingestion_mod,
        "record_claims_alignment_event",
        _record_alignment_event,
    )

    chunks = [
        {"text": "Chunk one text only.", "metadata": {"chunk_index": 0}},
        {"text": "Chunk two text only.", "metadata": {"chunk_index": 1}},
    ]

    claims = extract_claims_for_chunks(chunks, extractor_mode="openai", max_per_chunk=1)

    assert claims == []
    assert alignment_events == []
