import asyncio
import json
import types

import pytest

from tldw_Server_API.app.core.RAG.rag_service.claims import (
    ClaimsEngine,
    HeuristicSentenceExtractor,
    HybridClaimVerifier,
    Claim,
    Evidence,
)


class DummyDoc:
    def __init__(self, id, content, score=0.9):
        self.id = id
        self.content = content
        self.metadata = {}
        self.score = score


def test_heuristic_extractor_basic():
    extractor = HeuristicSentenceExtractor()
    text = "Paris is the capital of France. It has many museums."
    claims = asyncio.get_event_loop().run_until_complete(extractor.extract(text, max_claims=10))
    assert len(claims) >= 2
    assert any("capital of France" in c.text for c in claims)


def test_verifier_llm_fallback_supported(monkeypatch):
    # Analyze returns supported JSON
    def fake_analyze(api_name, input_data, custom_prompt_arg, api_key, system_message, temp, **kw):
        return json.dumps({"label": "supported", "confidence": 0.88, "rationale": "ok"})

    verifier = HybridClaimVerifier(fake_analyze)
    claim = Claim(id="c1", text="Paris is the capital of France")
    docs = [DummyDoc("d1", "Paris is the capital of France and largest city.")]

    result = asyncio.get_event_loop().run_until_complete(
        verifier.verify(claim, query="what is capital?", base_documents=docs, retrieve_fn=None, top_k=3)
    )

    assert result.label == "supported"
    assert result.confidence >= 0.8
    assert result.evidence


@pytest.mark.asyncio
async def test_claims_engine_end_to_end_llm_path():
    def fake_analyze(api_name, input_data, custom_prompt_arg, api_key, system_message, temp, **kw):
        # For extraction, return empty claims JSON to force heuristic fallback
        if isinstance(custom_prompt_arg, str) and custom_prompt_arg.startswith("Extract up to"):
            return json.dumps({"claims": []})
        return json.dumps({"label": "supported", "confidence": 0.92, "rationale": "ok"})

    engine = ClaimsEngine(fake_analyze)
    answer = "Paris is the capital of France. The Eiffel Tower is in Paris."
    docs = [
        DummyDoc("d1", "The capital of France is Paris."),
        DummyDoc("d2", "The Eiffel Tower stands in Paris, France."),
    ]

    out = await engine.run(
        answer=answer,
        query="What is the capital of France?",
        documents=docs,
        claims_top_k=3,
        claims_max=5,
    )

    assert "claims" in out and isinstance(out["claims"], list)
    assert out["summary"]["supported"] >= 1
