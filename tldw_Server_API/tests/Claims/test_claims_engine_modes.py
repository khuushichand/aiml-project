import asyncio
from typing import Any, Optional

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Claims.claims_engine import ClaimsEngine


class Doc:
    def __init__(self, id: str, content: str, score: float = 0.0):
        self.id = id
        self.content = content
        self.score = score


def _analyze_stub(api_name: str, input_data: Any, custom_prompt_arg: Optional[str] = None,
                  api_key: Optional[str] = None, system_message: Optional[str] = None,
                  temp: Optional[float] = None, **kwargs):
    # Extraction path (LLM-based extractor)
    if system_message and "extract" in system_message.lower() and isinstance(custom_prompt_arg, str):
        return '{"claims": [{"text": "Stub claim one."}]}'
    # Judge path
    if system_message and "fact-checking judge" in system_message:
        return '{"label": "supported", "confidence": 0.9, "rationale": "stub"}'
    return '{"claims": []}'


@pytest.mark.unit
def test_claims_engine_llm_only_labels_supported():
    engine = ClaimsEngine(_analyze_stub)
    answer = "Alpha. Beta."
    query = "Q"
    documents = [Doc("d1", "Alpha Beta context", 0.5)]

    async def _run():
        result = await engine.run(
            answer=answer,
            query=query,
            documents=documents,
            claim_extractor="auto",
            claim_verifier="llm",
            claims_top_k=2,
            claims_conf_threshold=0.5,
            claims_max=5,
        )
        claims = result.get("claims") or []
        assert claims, "No claims returned"
        assert all(c.get("label") in {"supported", "refuted", "nei"} for c in claims)
        # Our stub judge always marks supported
        assert any(c.get("label") == "supported" for c in claims)

    asyncio.run(_run())


@pytest.mark.unit
def test_claims_engine_nli_only_without_model_returns_nei():
    # No transformers/NLI model available in test env, so NLI path should return NEI without LLM fallback
    def _analyze_noop(api_name: str, input_data: Any, custom_prompt_arg: Optional[str] = None,
                      api_key: Optional[str] = None, system_message: Optional[str] = None,
                      temp: Optional[float] = None, **kwargs):
        return '{"claims": []}'

    engine = ClaimsEngine(_analyze_noop)
    answer = "Acme was founded in 2000."
    query = "When was Acme founded?"
    documents = [Doc("d1", "Acme context", 0.1)]

    async def _run():
        result = await engine.run(
            answer=answer,
            query=query,
            documents=documents,
            claim_extractor="auto",  # LLM path returns empty -> fallback to heuristic
            claim_verifier="nli",
            claims_top_k=2,
            claims_conf_threshold=0.7,
            claims_max=3,
        )
        claims = result.get("claims") or []
        assert claims, "Expected at least one heuristic claim"
        assert all(c.get("label") == "nei" for c in claims)

    asyncio.run(_run())
